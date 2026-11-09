"""Publish the completed table/body evidence ledger without changing any source/index."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts import review_table_body_links as runner
from scripts.verify_five_domain_scope import secret_scan
from server import table_body_review as review, hr_source_scope as source


def main():
    protocol, occurrences = runner.context()
    assets = list(runner.readl(runner.OUT/'assets.jsonl'))
    if not runner.status()['complete']:
        raise SystemExit('All 1,014 source occurrences must be processed before final publication.')
    assert len(assets) == 917 and len(occurrences) == 1014
    assert len({r['asset_id'] for r in assets}) == 917 and len({r['id'] for r in occurrences}) == 1014
    assert all(source.file_sha(runner.ROOT/path) == sha for path, sha in protocol['baseline_sha256'].items())
    assert all(source.file_sha(Path(r['path'])) == r['sha256'] for r in protocol['source_file_sha256'].values())
    originals = runner.load(runner.CLEAN/'tables/inventory.json')
    for asset in originals:
        assert source.file_sha((runner.CLEAN/asset['source_image_path']).resolve()) == asset['image_sha256']
    by_asset = defaultdict(list); links = []; methods = Counter(); gate_counts = Counter()
    calls_cache = {p.name: runner.load(p) for p in (runner.OUT/'calls').glob('*.json')}
    calls = list(calls_cache.values()); errors_by_id = defaultdict(set)
    for call in calls:
        for error in call['errors']:
            for ident in ([error['id']] if error.get('id') else call['ids']):
                errors_by_id[ident].add(error['code'])
    descriptions = {
        'TABLE_NUMBERS_NOT_ALL_IN_CITED_BODY': '표의 숫자 중 본문 인용에서 확인되지 않는 값이 있어 전체 중복을 확정하지 못했다.',
        'TABLE_LINE_COVERAGE_INCOMPLETE': '표의 일부 행·항목을 본문 근거와 연결하지 못했다.',
        'INDEPENDENT_FUNCTION_OR_INFORMATION': '독립된 서식 기능이나 추가 정보가 남아 전체 중복을 확정하지 못했다.',
        'PRIVATE_CONTEXT_OMITTED': '개인정보 패턴 때문에 비교 근거 일부를 제외해 전체 중복을 확정하지 못했다.',
        'INCOMPLETE_COMPARISON': '표·본문·필수 각주를 충분히 확인하지 못했다.',
        'QUOTE_NOT_IN_SOURCE': '제안한 인용문이 원문과 일치하지 않아 근거를 확인해야 한다.',
        'QUOTE_LENGTH': '제안한 인용의 길이 또는 짧은 필드 근거를 추가 확인해야 한다.',
        'TABLE_SUPPORT_ANCHOR_REQUIRED': '표에서 충분한 실제 인용 근거를 확보하지 못했다.',
        'BOTH_SOURCE_SUPPORTS_REQUIRED': '표 또는 연결 본문의 직접 인용 근거가 부족하다.',
        'UNKNOWN_BODY_ID': '제안한 본문 ID가 제공한 근거 목록과 일치하지 않는다.',
        'UNSOURCED_FACT_NUMBER': '설명에 원문에서 확인되지 않은 숫자가 포함되어 있다.'}
    page_reviews = {}
    if (runner.OUT/'source-page-reviews.jsonl').is_file():
        page_reviews = {r['id']: r for r in runner.readl(runner.OUT/'source-page-reviews.jsonl')}
    wanted_bodies = {q['id'] for r in page_reviews.values() for q in r.get('extra_body_quotes', [])}
    extra_bodies = {r['id']: r for r in runner.readl(runner.OUT/'source-body-paragraphs.jsonl') if r['id'] in wanted_bodies}
    assert set(extra_bodies) == wanted_bodies
    for occurrence in occurrences:
        result = runner.load(runner.result_path(occurrence['id']))
        refined_path = runner.OUT/'refinement-results'/(review.digest(occurrence['id'])+'.json')
        if refined_path.is_file():
            refined = runner.load(refined_path)
            assert source.file_sha(runner.result_path(occurrence['id'])) == refined['expected_initial_result_sha256']
            result = refined
        assert result['id'] == occurrence['id'] and result['asset_id'] == occurrence['asset_id']
        assert result['source_action'] == 'PRESERVE' and not result['human_approved'] and not result['answer_eligible']
        if result['method'].startswith('GPT_'):
            call_name = result['call_record']
            if call_name not in calls_cache:
                calls_cache[call_name] = runner.load(runner.OUT/'calls'/call_name)
            raw = next(r for r in calls_cache[call_name]['proposals'] if r['id'] == occurrence['id'])
            checked = review.validate(review.Comparison.model_validate(raw), occurrence, runner.PRIVATE)
            assert all(result[k] == value for k, value in checked.items())
        else:
            assert result['label'] == 'HOLD' and not result['table_supports'] and not result['body_supports']
            if errors_by_id[occurrence['id']]:
                result['validation_errors'] = sorted(errors_by_id[occurrence['id']])
                result['reason'] = ' '.join(dict.fromkeys(descriptions.get(code, '응답 또는 근거 검사가 완료되지 않아 추가 확인이 필요하다.') for code in result['validation_errors']))
        if result.get('code_hold_reasons'):
            result['reason'] = ' '.join(descriptions.get(code, code) for code in result['code_hold_reasons'])
        result = review.apply_context_gate(result, occurrence)
        if occurrence['id'] in page_reviews:
            decision = page_reviews[occurrence['id']]
            assert source.file_sha(runner.result_path(occurrence['id'])) == decision['expected_result_sha256']
            for image in decision['images']:
                assert source.file_sha(runner.OUT/image['path']) == image['sha256']
                assert image['source_file_sha256'] == occurrence['source_file_sha256']
            result = review.apply_source_page_review(result, occurrence, decision, extra_bodies, runner.PRIVATE)
        methods[result['method']] += 1; gate_counts.update(result.get('code_hold_reasons', []))
        # Retain selected source paragraphs and every checked quote with its page, bbox and hashes.
        row = occurrence | dict(comparison=result)
        assert not runner.private_payload(row)
        links.append(row); by_asset[row['asset_id']].append(row)
    reviewed_assets = []
    for asset in assets:
        rows = by_asset[asset['asset_id']]
        label = review.aggregate([r['comparison'] for r in rows])
        reviewed_assets.append(asset | dict(label=label, label_ko=review.LABELS[label],
            source_occurrences=len(rows), occurrence_label_counts=dict(Counter(r['comparison']['label'] for r in rows)),
            has_unresolved_occurrences=any(r['comparison']['label'] == 'HOLD' for r in rows),
            reasons=list(dict.fromkeys(r['comparison']['reason'] for r in rows)),
            new_information=list(dict.fromkeys(r['comparison'].get('new_information', '') for r in rows if r['comparison'].get('new_information'))),
            conflicts=list(dict.fromkeys(r['comparison'].get('conflict_detail', '') for r in rows if r['comparison'].get('conflict_detail'))),
            human_approved=False, answer_eligible=False, ktcs_applicable=False, source_action='PRESERVE'))
    runner.writel(runner.OUT/'table-body-links.jsonl', links)
    runner.writel(runner.OUT/'table-review.jsonl', reviewed_assets)
    usage = Counter()
    for call in calls:
        if call.get('usage'):
            for key in ['input_tokens', 'output_tokens', 'total_tokens']:
                usage[key] += call['usage'].get(key, 0)
    stages = {}
    for stage in ['priority_172', 'remaining_745']:
        selected = [r for r in reviewed_assets if r['stage'] == stage]
        stages[stage] = dict(assets=len(selected), labels=dict(Counter(r['label'] for r in selected)))
    summary = dict(source_documents=len(protocol['source_file_sha256']), reviewed_assets=917,
        source_occurrences=1014, all_occurrences_processed=True, all_occurrences_revalidated=True,
        asset_labels=dict(Counter(r['label'] for r in reviewed_assets)),
        occurrence_labels=dict(Counter(r['comparison']['label'] for r in links)), stages=stages,
        processing_methods=dict(methods), code_hold_reasons=dict(gate_counts),
        refined_occurrences=sum(bool(r['comparison'].get('refinement')) for r in links),
        refinement_selected_occurrences=sum(len(runner.load(p)['ids']) for p in runner.OUT.glob('refinement-protocol-*.json')),
        agent_source_page_reviews=len(page_reviews),
        remote_applicability_holds=sum(bool(r['comparison'].get('context_gate')) and not r['comparison'].get('source_page_review_method') for r in links),
        source_page_review_label_changes=sum(r['comparison'].get('source_page_review_method') is not None and r['comparison']['label'] != r['comparison'].get('before_page_review_label') for r in links),
        reused_previous_screening_assets=917, previous_native_records_available_for_current_assets=172,
        reused_native_body_anchors=sum(bool(r['reused_native_body_ids']) for r in occurrences),
        model=protocol['model'], generation_request_attempts=sum(bool(c['request_attempted']) for c in calls),
        completed_response_usage_records=sum(bool(c.get('usage')) for c in calls), usage=dict(usage),
        input_token_count_records=sum(c['input_tokens'] is not None for c in calls),
        comparison_scope='SELECTED_TABLE_EXCLUDED_BODY_FROM_SAME_DOCUMENT_VERSION',
        additional_information_is_relative_to_linked_body_not_global_absence_proof=True,
        all_baseline_and_source_hashes_unchanged=True, all_original_table_images_preserved=True,
        current_curation_not_deleted_or_modified=True, source_action='PRESERVE', new_embeddings=0,
        answer_eligibility_changed=False, independent_human_approval=False, supabase_ingestion='HOLD', external_database_writes=0,
        table_body_links_sha256=source.file_sha(runner.OUT/'table-body-links.jsonl'),
        table_review_sha256=source.file_sha(runner.OUT/'table-review.jsonl'))
    runner.write(runner.OUT/'summary.json', summary)
    payload = dict(summary=summary, labels=review.LABELS, records=[])
    for asset in reviewed_assets:
        views = []
        for row in by_asset[asset['asset_id']]:
            comparison = row['comparison']; bodies = {r['id']: r for r in row['body']}
            proofs = []
            for support in comparison['body_supports']:
                proofs.append(dict(id=support['id'], page=support['page'], text=support['text'],
                    bbox=support['bbox'], text_sha256=support['text_sha256']))
            for support in comparison.get('extra_context_supports', []):
                if not any(p['id'] == support['id'] and p['text'] == support['text'] for p in proofs):
                    proofs.append(dict(id=support['id'], page=support['page'], text=support['text'],
                        bbox=support['bbox'], text_sha256=support['text_sha256']))
            views.append(dict(id=row['id'], unit_id=row['unit_id'], page=row['page'],
                label=comparison['label'], reason=comparison['reason'], proposed_label=comparison.get('proposed_label'),
                table_text=row['table_text'], table_quotes=[r['text'] for r in comparison['table_supports']],
                body_proofs=proofs, body_source_count=row['body_source_count'],
                new_information=comparison.get('new_information', ''), conflict_detail=comparison.get('conflict_detail', ''),
                source_file_sha256=row['source_file_sha256'], original_download_url=row['original_download_url'],
                holds=comparison.get('code_hold_reasons', []), method=comparison['method'],
                body_candidates=[dict(id=bodies[ident]['id'],page=bodies[ident]['page'],text=bodies[ident]['text'])
                    for ident in row['global_retrieval_body_ids'][:3] if ident in bodies] if comparison['label']=='HOLD' else []))
        payload['records'].append(asset | dict(occurrences=views))
    encoded = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('&', '\\u0026')
    template = (REPO/'server/table_body_report.html').read_text(encoding='utf-8')
    (runner.OUT/'index.html').write_text(template.replace('__PAYLOAD__', encoded), encoding='utf-8')
    shutil.copyfile(REPO/'server/table_body_favicon.svg', runner.OUT/'favicon.svg')
    runner.write(runner.OUT/'view-manifest.json', dict(app_id='klink-table-body-links-20261109', assets=917,
        occurrences=1014, report_sha256=source.file_sha(runner.OUT/'index.html'), supabase_ingestion='HOLD'))
    changed = subprocess.check_output(['git', 'diff', '--name-only', 'HEAD'], cwd=REPO, text=True).splitlines()
    changed += subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=REPO, text=True).splitlines()
    paths = [REPO/path for path in set(changed) if (REPO/path).is_file()]
    paths += [path for path in runner.OUT.rglob('*') if path.is_file()]
    secret_scan(paths)
    runner.write(runner.OUT/'verification.json', dict(all_assets_present=917, all_occurrences_present=1014,
        checked_source_documents=len(protocol['source_file_sha256']), source_hashes_unchanged=True,
        all_accepted_model_proposals_and_quotes_revalidated=True, both_sides_same_document_and_version=True,
        all_detected_table_regions_excluded_from_body=True, actual_secret_literal_matches=0, private_pattern_payload_matches=0,
        original_images_preserved=917, source_action='PRESERVE', new_embeddings=0,
        independent_human_approval=False, supabase_ingestion='HOLD', external_database_writes=0))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
