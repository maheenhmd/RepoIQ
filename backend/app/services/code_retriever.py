"""Budgeted evidence packing over the existing hybrid retriever's ranked results."""
import hashlib
import json
import logging

from app.integrations.llm_client import LLMError


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def input_tokens(messages, schema):
    # Count actual message content, not the HTTP JSON wrapper escaping it again.
    # Include schema conservatively even if the provider uses it only as grammar.
    size = sum(len(m['content'].encode('utf-8')) for m in messages)
    return (size + len(compact(schema).encode('utf-8')) + 1) // 2


def pack_context(sources, state, schema, system, settings):
    # No compatible Ollama tokenizer is exposed locally. Conservative byte estimate
    # plus template margin; never load the unrelated embedding tokenizer.
    budget = settings.ollama_context_tokens - settings.ollama_max_tokens - 512
    history = state.get('history', [])
    state = dict(state, history=[], excerpts=[], evidence_limited=True)
    schema = dict(schema, properties=dict(schema['properties']))
    schema['properties']['source_ids'] = dict(schema['properties']['source_ids'])

    def payload(selected, past):
        schema['properties']['source_ids']['items'] = {'type': 'string', 'enum': [s.source_id for s in selected]}
        body = dict(state, history=past, excerpts=[{
            'source_id': s.source_id, 'file_path': s.file_path, 'symbol': s.symbol_name,
            'start_line': s.start_line, 'end_line': s.end_line, 'content': s.content,
        } for s in selected])
        # Active question and full answer remain explicit, unchanged fields.
        messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': compact(body)}]
        cost = input_tokens(messages, schema)
        return messages, cost

    _, fixed = payload([], [])
    def diagnostic(validation, cost, evidence=0):
        logging.getLogger(__name__).info(
            'context_pack_v2 validation=%s context_limit=%d estimated_input_tokens=%d reserved_output_tokens=%d packed_evidence_tokens=%d template_reserve=512',
            validation, settings.ollama_context_tokens, cost, settings.ollama_max_tokens, evidence)
    if fixed >= budget:
        diagnostic('essential_prompt_overflow', fixed)
        raise LLMError('Question and answer exceed model capacity; shorten answer or increase context limit', 422)
    selected, ids, hashes = [], set(), set()
    chars = 0
    for source in sources:
        if len(selected) >= settings.interview_retrieval_count:
            break
        digest = hashlib.sha256(source.content.encode('utf-8')).digest()
        if source.chunk_id in ids or digest in hashes:
            continue
        ids.add(source.chunk_id)
        hashes.add(digest)
        _, cost = payload([*selected, source], [])
        if cost <= budget and chars + len(source.content) <= settings.interview_context_chars:
            selected.append(source)
            chars += len(source.content)
        # Skip oversized candidates first so shorter complete implementations win.

    if not selected:
        # A truthful contiguous prefix is preferable to rejecting an answer because
        # the highest-ranked chunk is large. Never invent or join noncontiguous lines.
        for source in sources:
            lines = source.content.splitlines(keepends=True)
            kept = []
            used_chars = 0
            # Incremental upper estimate of nested JSON string cost avoids
            # serializing every growing prefix. Final payload is checked below.
            empty = source.model_copy(update={'content': '', 'end_line': source.start_line})
            _, prefix_cost = payload([empty], [])
            prefix_cost += 16  # line-number growth and rounding margin
            for line in lines:
                line_cost = (len(compact(compact(line)).encode('utf-8')) + 1) // 2
                if prefix_cost + line_cost > budget or used_chars + len(line) > settings.interview_context_chars:
                    break
                kept.append(line)
                prefix_cost += line_cost
                used_chars += len(line)
            if not kept and lines:
                # One unusually long line must not eliminate all available evidence.
                low, high = 0, min(len(lines[0]), settings.interview_context_chars)
                while low < high:
                    middle = (low + high + 1) // 2
                    excerpt = source.model_copy(update={'content': lines[0][:middle],
                        'end_line': source.start_line})
                    _, cost = payload([excerpt], [])
                    if cost <= budget:
                        low = middle
                    else:
                        high = middle - 1
                if low:
                    kept = [lines[0][:low]]
            if kept and ''.join(kept).strip():
                selected = [source.model_copy(update={'content': ''.join(kept),
                    'end_line': min(source.end_line, source.start_line + len(kept) - 1)})]
                break
    if not selected:
        diagnostic('no_evidence_fits', fixed)
        raise LLMError('No cited evidence line fits with the question and answer; shorten answer or increase context limit', 422)
    past = []
    for entry in reversed(history):
        _, cost = payload(selected, [entry, *past])
        if cost <= budget:
            past.insert(0, entry)
        else:
            break
    messages, cost = payload(selected, past)
    if cost > budget:
        diagnostic('final_prompt_overflow', cost)
        raise LLMError('Interview prompt exceeds configured context capacity', 422)
    _, evidence_cost = payload(selected, [])
    # Restore the exact final schema/messages after measuring evidence overhead.
    messages, cost = payload(selected, past)
    diagnostic('passed', cost, max(0, evidence_cost - fixed))
    return selected, messages, schema, cost
