"""Dependency-free Track 2 validation and scoring."""
import json
import re
from pathlib import Path

CODES = {
    'DIFFERENT_ENTITY': {'TEMPORAL_IMPOSSIBILITY', 'DOB_MISMATCH', 'LOCATION_MISMATCH', 'NAME_MISMATCH_VERIFIED', 'ENTITY_TYPE_MISMATCH', 'DECEASED'},
    'SAME_ENTITY': {'NAME_DOB_LOCATION_MATCH', 'NAME_DOB_MATCH', 'NAME_LOCATION_MATCH'},
    'REVIEW': {'INSUFFICIENT_DATA', 'AMBIGUOUS_CUSTOMER_RECORD'},
}
COST = {'DIFFERENT_ENTITY': dict(zip(CODES, (0, 3, 3))),
        'SAME_ENTITY': dict(zip(CODES, (60, 0, 2))),
        'REVIEW': dict(zip(CODES, (60, 2, 0)))}
FIELDS = {'hit_id', 'alert_id', 'decision', 'reason_code', 'customer_record_id', 'reason', 'evidence'}


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def read(path):
    result = {}
    with Path(path).open(encoding='utf-8-sig') as stream:
        for number, line in enumerate(stream, 1):
            try:
                row = json.loads(line, object_pairs_hook=_object,
                                 parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
                if not isinstance(row, dict) or not isinstance(row.get('hit_id'), str) or not row['hit_id']:
                    raise ValueError('expected object with nonempty hit_id')
                if row['hit_id'] in result:
                    raise ValueError('duplicate hit_id')
                result[row['hit_id']] = row
            except ValueError as exc:
                raise ValueError(f'{path}:{number}: {exc}') from exc
    if not result:
        raise ValueError(f'{path}: empty file')
    return result


def validate(rows, hits=None):
    errors, warnings = [], []
    for hit, row in rows.items():
        def error(message):
            errors.append(f'{hit}: {message}')
        if FIELDS - row.keys():
            error(f'missing fields: {sorted(FIELDS - row.keys())}')
        for field in ('alert_id', 'decision', 'reason_code', 'reason'):
            if not isinstance(row.get(field), str) or not row[field].strip():
                error(f'{field} must be a nonempty string')
        decision = row.get('decision')
        if not isinstance(decision, str) or decision not in CODES:
            error('invalid decision')
        elif not isinstance(row.get('reason_code'), str) or row['reason_code'] not in CODES[decision]:
            error('reason_code does not belong to decision')
        customer = row.get('customer_record_id')
        if customer is not None and (not isinstance(customer, str) or not customer.strip()):
            error('customer_record_id must be nonempty string or null')
        evidence = row.get('evidence')
        if not isinstance(evidence, list) or any(not isinstance(x, str) or not x.strip() for x in evidence):
            error('evidence must be an array of nonempty record ID strings')
        reason = row.get('reason')
        if isinstance(reason, str):
            sentences = [s for s in re.split(r'(?<=[.!?])\s+', reason.strip()) if s]
            if not 2 <= len(sentences) <= 4:
                warnings.append(f'{hit}: expected 2–4 sentences (heuristic count {len(sentences)}); review manually')
        if hits is not None and hit in hits and row.get('alert_id') != hits[hit].get('alert_id'):
            error('alert_id does not match hits.jsonl')
    if hits is not None:
        for hit in sorted(hits.keys() - rows.keys()):
            errors.append(f'{hit}: missing prediction')
        for hit in sorted(rows.keys() - hits.keys()):
            errors.append(f'{hit}: unknown hit')
    return errors, warnings


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def score(predictions, labels):
    missing = labels.keys() - predictions.keys()
    if missing:
        raise ValueError(f'missing labeled predictions: {sorted(missing)}')
    total = baseline = unsafe = correct = reasons = reason_count = correct_reasons = 0
    cleared = true_clear = same = true_same = reviews = different = 0
    for hit, label in labels.items():
        truth = label.get('decision')
        if not isinstance(truth, str) or truth not in CODES:
            raise ValueError(f'{hit}: invalid label decision')
        prediction = predictions[hit]
        if 'alert_id' in label and label['alert_id'] != prediction['alert_id']:
            raise ValueError(f'{hit}: label alert_id mismatch')
        decision = prediction['decision']
        total += COST[truth][decision]
        baseline += COST[truth]['REVIEW']
        unsafe += decision == 'DIFFERENT_ENTITY' and truth != 'DIFFERENT_ENTITY'
        cleared += decision == 'DIFFERENT_ENTITY'
        true_clear += decision == truth == 'DIFFERENT_ENTITY'
        same += truth == 'SAME_ENTITY'
        different += truth == 'DIFFERENT_ENTITY'
        true_same += decision == truth == 'SAME_ENTITY'
        reviews += decision == 'REVIEW'
        correct += decision == truth
        accepted = label.get('reason_codes', [label['reason_code']] if 'reason_code' in label else None)
        if accepted is not None:
            if not isinstance(accepted, list) or not accepted or any(not isinstance(x, str) or x not in CODES[truth] for x in accepted):
                raise ValueError(f'{hit}: invalid label reason_codes')
            reason_count += 1
            reasons += decision == truth and prediction['reason_code'] in accepted
            correct_reasons += decision == truth
    return dict(scored_hits=len(labels), unscored_predictions=len(predictions)-len(labels),
                cost=total, all_review_cost=baseline,
                decision_score=max(0, 1-total/baseline) if baseline else None,
                unsafe_clearances=unsafe, review_rate=ratio(reviews, len(labels)),
                same_entity_recall=ratio(true_same, same), clearance_precision=ratio(true_clear, cleared),
                false_positives_cleared=ratio(true_clear, different),
                decision_accuracy=ratio(correct, len(labels)),
                reason_code_accuracy=ratio(reasons, reason_count),
                reason_code_accuracy_on_correct_decisions=ratio(reasons, correct_reasons))
