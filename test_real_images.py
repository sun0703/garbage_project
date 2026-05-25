"""
真实垃圾图片多模态融合识别测试
"""
import sys, os

sys.path.insert(0, '.')

from multimodal_fusion import MultiModalFusionClassifier
from PIL import Image


def main():
    classifier = MultiModalFusionClassifier()

    test_images = [
        '模型训练/datasets/rubbish/images/IMG_20210312_201546.jpg',
        '模型训练/datasets/rubbish/images/IMG_20210312_201535.jpg',
        '模型训练/datasets/rubbish/images/IMG_20210312_201433.jpg',
        '模型训练/datasets/rubbish/images/IMG_20210312_201416.jpg',
        '模型训练/datasets/rubbish/images/IMG_20210312_201325.jpg',
        '模型训练/datasets/rubbish/images/IMG_20210312_201322.jpg',
        '模型训练/datasets/rubbish/images/IMG_20210312_201247.jpg',
        '模型训练/datasets/rubbish/images/IMG_20210311_214045.jpg',
    ]

    print('=' * 70)
    print('  真实垃圾图片 - 多模态融合识别测试')
    print('=' * 70)

    for img_path in test_images:
        if not os.path.exists(img_path):
            continue

        sep = '-' * 60
        print(f'\n{sep}')
        print(f'  图片: {os.path.basename(img_path)}')
        print(sep)

        try:
            img = Image.open(img_path)
            result = classifier.predict(img)

            print(f'\n  三模态结果:')
            if result.yolo_result:
                y = result.yolo_result
                print(f'    [YOLO]     {y.fine_class_name_cn} ({y.category_name}) {y.confidence:.0%}')
            if result.sahi_result:
                s = result.sahi_result
                print(f'    [SAHI]     {s.fine_class_name_cn} ({s.category_name}) {s.confidence:.0%}')
            if result.transformer_result:
                c = result.transformer_result
                print(f'    [Cascade]  {c.fine_class_name_cn} ({c.category_name}) {c.confidence:.0%}')

            vc = result.fusion_details.get('vote_count', '?')
            tm = result.fusion_details.get('total_models', '?')
            fcat = result.final_prediction.category_name
            fname = result.final_prediction.fine_class_name_cn
            fconf = result.final_prediction.confidence
            consis = result.consistency_score
            ms = result.total_inference_time_ms

            print(f'  +--- 最终结果 ---+')
            print(f'  | 预测: {fname} ({fcat})')
            print(f'  | 置信度: {fconf:.1%}')
            print(f'  | 一致性: {consis:.0%} ({vc}/{tm}模型)')
            print(f'  | 耗时: {ms:.0f}ms')

        except Exception as e:
            import traceback
            print(f'  错误: {e}')
            traceback.print_exc()

    print('\n' + '=' * 70)
    print('  测试完成!')
    print('=' * 70)


if __name__ == '__main__':
    main()
