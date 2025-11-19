import json
import re
from typing import Dict, Set, List, Tuple
from pathlib import Path


def parse_ground_truth(gt_text: str) -> Dict[str, Set[int]]:
    """
    정답지 텍스트를 파싱하여 딕셔너리로 변환
    
    Args:
        gt_text: 정답지 텍스트 (예: "00:00:28 1,4")
    
    Returns:
        {timestamp: set of object ids}
    """
    ground_truth = {}
    for line in gt_text.strip().split('\n'):
        if not line.strip():
            continue
        parts = line.strip().split()
        if len(parts) >= 2:
            timestamp = parts[0]
            obj_ids = set(int(x.strip()) for x in parts[1].split(','))
            ground_truth[timestamp] = obj_ids
    return ground_truth


def parse_prediction_json(json_path: str) -> Dict[str, Set[int]]:
    """
    예측 결과 JSON 파일을 파싱
    
    Args:
        json_path: JSON 파일 경로
    
    Returns:
        {timestamp: set of object ids}
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    predictions = {}
    
    for chunk in data.get('chunk_responses', []):
        content = chunk.get('content', '')
        
        # JSON 코드 블록에서 실제 JSON 추출
        json_match = re.search(r'```json\s*(\[.*?\])\s*```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            try:
                items = json.loads(json_str)
                for item in items:
                    if isinstance(item, dict):
                        for timestamp, obj_ids in item.items():
                            predictions[timestamp] = set(obj_ids)
            except json.JSONDecodeError as e:
                print(f"JSON 파싱 오류: {e}")
                print(f"내용: {json_str}")
    
    return predictions


def calculate_metrics(ground_truth: Dict[str, Set[int]], 
                     predictions: Dict[str, Set[int]]) -> Tuple[float, float, float, Dict]:
    """
    Precision, Recall, F1 Score 계산
    
    Args:
        ground_truth: 정답 데이터
        predictions: 예측 데이터
    
    Returns:
        (precision, recall, f1, details)
    """
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    
    details = {
        'correct': [],
        'missing_timestamps': [],
        'extra_timestamps': [],
        'incorrect_objects': []
    }
    
    all_timestamps = set(ground_truth.keys()) | set(predictions.keys())
    
    for timestamp in sorted(all_timestamps):
        gt_objects = ground_truth.get(timestamp, set())
        pred_objects = predictions.get(timestamp, set())
        
        if timestamp not in ground_truth:
            # 예측했지만 정답에 없는 타임스탬프
            details['extra_timestamps'].append({
                'timestamp': timestamp,
                'predicted': sorted(pred_objects)
            })
            false_positives += len(pred_objects)
        elif timestamp not in predictions:
            # 정답에 있지만 예측하지 못한 타임스탬프
            details['missing_timestamps'].append({
                'timestamp': timestamp,
                'ground_truth': sorted(gt_objects)
            })
            false_negatives += len(gt_objects)
        else:
            # 둘 다 있는 경우
            correct_objects = gt_objects & pred_objects
            extra_objects = pred_objects - gt_objects
            missing_objects = gt_objects - pred_objects
            
            true_positives += len(correct_objects)
            false_positives += len(extra_objects)
            false_negatives += len(missing_objects)
            
            if gt_objects == pred_objects:
                details['correct'].append({
                    'timestamp': timestamp,
                    'objects': sorted(gt_objects)
                })
            else:
                details['incorrect_objects'].append({
                    'timestamp': timestamp,
                    'ground_truth': sorted(gt_objects),
                    'predicted': sorted(pred_objects),
                    'correct': sorted(correct_objects),
                    'extra': sorted(extra_objects),
                    'missing': sorted(missing_objects)
                })
    
    # Precision, Recall, F1 계산
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    return precision, recall, f1, details


def print_comparison_report(precision: float, recall: float, f1: float, details: Dict):
    """비교 결과 리포트 출력"""
    print("=" * 80)
    print("Object Detection 비교 결과")
    print("=" * 80)
    print(f"\n📊 성능 지표:")
    print(f"  Precision: {precision:.4f} ({precision*100:.2f}%)")
    print(f"  Recall:    {recall:.4f} ({recall*100:.2f}%)")
    print(f"  F1 Score:  {f1:.4f} ({f1*100:.2f}%)")
    
    print(f"\n✅ 완전히 일치하는 타임스탬프: {len(details['correct'])}개")
    for item in details['correct']:
        print(f"  {item['timestamp']}: {item['objects']}")
    
    if details['incorrect_objects']:
        print(f"\n⚠️  Object ID가 다른 타임스탬프: {len(details['incorrect_objects'])}개")
        for item in details['incorrect_objects']:
            print(f"  {item['timestamp']}:")
            print(f"    정답:   {item['ground_truth']}")
            print(f"    예측:   {item['predicted']}")
            if item['extra']:
                print(f"    추가됨: {item['extra']}")
            if item['missing']:
                print(f"    누락됨: {item['missing']}")
    
    if details['missing_timestamps']:
        print(f"\n❌ 누락된 타임스탬프: {len(details['missing_timestamps'])}개")
        for item in details['missing_timestamps']:
            print(f"  {item['timestamp']}: {item['ground_truth']} (예측 없음)")
    
    if details['extra_timestamps']:
        print(f"\n➕ 추가로 예측된 타임스탬프: {len(details['extra_timestamps'])}개")
        for item in details['extra_timestamps']:
            print(f"  {item['timestamp']}: {item['predicted']} (정답에 없음)")
    
    print("\n" + "=" * 80)


def main():
    # 정답지 (사용자가 제공한 데이터)
    ground_truth_text = """
00:00:28 1,4
00:00:30 2,4
00:00:31 2,4
00:00:33 3,4
00:00:39 1,4
00:00:40 1,4
00:00:41 1,3
00:00:42 1,3
00:00:51 2,4
00:00:54 2,3
00:00:56 1,2
00:00:57 1,2
    """
    
    # 예측 결과 파일 경로
    prediction_file = Path(__file__).parent.parent / "outputs" / "gpt_video_21_20251114_010528.json"
    
    # 파싱
    ground_truth = parse_ground_truth(ground_truth_text)
    predictions = parse_prediction_json(str(prediction_file))
    
    # 메트릭 계산
    precision, recall, f1, details = calculate_metrics(ground_truth, predictions)
    
    # 결과 출력
    print_comparison_report(precision, recall, f1, details)
    
    # 결과를 JSON으로도 저장
    result_file = Path(__file__).parent.parent / "compare_outputs" / "comparison_result.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump({
            'metrics': {
                'precision': precision,
                'recall': recall,
                'f1_score': f1
            },
            'details': details
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n상세 결과가 저장되었습니다: {result_file}")


if __name__ == "__main__":
    main()
