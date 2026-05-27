"""全局常量：路径、类别映射、关键词等"""

from pathlib import Path
import numpy as np

# 路径常量
BASE_DIR = Path(__file__).parent.parent

# 40类垃圾分类专用YOLOv8m模型（2025年最新，mAP@0.5: 91%）
MODEL_PATH = BASE_DIR / "models" / "garbage_yolov8m_best.pt"
USE_YOLO_PT_MODEL = True

# 备用：旧版ONNX模型
# MODEL_PATH = BASE_DIR / "models" / "yolov8_coco.onnx"
# USE_YOLO_PT_MODEL = False
VOCAB_PATH = BASE_DIR / "data" / "waste.json"
STATIC_DIR = BASE_DIR / "static"
INDEX_HTML_PATH = STATIC_DIR / "index.html"

# 模型推理尺寸
INPUT_SIZE = (224, 224)
YOLO_INPUT_SIZE = (640, 640)
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# 垃圾分类4个类别（中国标准）
WASTE_CATEGORIES = {
    0: {"name": "厨余垃圾", "color": "#8B4513", "icon": "🗑️", "bin_color": "棕色"},
    1: {"name": "可回收物", "color": "#007bff", "icon": "♻️", "bin_color": "蓝色"},
    2: {"name": "其他垃圾", "color": "#333333", "icon": "🗑️", "bin_color": "灰色/黑色"},
    3: {"name": "有害垃圾", "color": "#dc3545", "icon": "☠️", "bin_color": "红色"},
}

# YOLOv8 7类模型类别
YOLOV8_7CLASSES = {
    0: {"name": "banana-peel", "name_cn": "香蕉皮", "category": 0},
    1: {"name": "glass", "name_cn": "玻璃", "category": 1},
    2: {"name": "metal", "name_cn": "金属", "category": 1},
    3: {"name": "orange-peel", "name_cn": "橘子皮", "category": 0},
    4: {"name": "paper", "name_cn": "纸张", "category": 1},
    5: {"name": "plastic", "name_cn": "塑料", "category": 1},
    6: {"name": "styrofoam", "name_cn": "泡沫塑料", "category": 2},
}

# 40类细粒度垃圾分类映射（garbage_detect YOLOv8m模型）
# 来源: https://github.com/liangxi2004/garbage_detect
GARBAGE_40CLASSES = {
    # 其他垃圾 (Other Trash) - category 2
    0: {"name": "Other Trash/Disposable Fast Food Box", "name_cn": "一次性快餐盒", "category": 2},
    1: {"name": "Other Trash/Dirty Plastic", "name_cn": "脏塑料", "category": 2},
    2: {"name": "Other Trash/Cigarette Butts", "name_cn": "烟蒂", "category": 2},
    3: {"name": "Other Trash/toothpicks", "name_cn": "牙签", "category": 2},
    4: {"name": "Other Trash/Crushed Flower Pots and Plates", "name_cn": "碎花盆和盘子", "category": 2},
    5: {"name": "Other Trash/Bamboo Chopsticks", "name_cn": "竹筷", "category": 2},

    # 厨余垃圾 (Kitchen Waste) - category 0
    6: {"name": "Kitchen Waste/Leftover Food", "name_cn": "剩菜剩饭", "category": 0},
    7: {"name": "Kitchen Waste/Large Bones", "name_cn": "大骨头", "category": 0},
    8: {"name": "Kitchen Waste/Fruit Peels", "name_cn": "果皮", "category": 0},
    9: {"name": "Kitchen Waste/Fruit Flesh", "name_cn": "果肉/果核", "category": 0},
    10: {"name": "Kitchen Waste/Tea Leaves", "name_cn": "茶叶", "category": 0},
    11: {"name": "Kitchen Waste/Vegetable Leaves and Roots", "name_cn": "蔬菜叶和根", "category": 0},
    12: {"name": "Kitchen Waste/Eggshells", "name_cn": "蛋壳", "category": 0},
    13: {"name": "Kitchen Waste/Fish Bones", "name_cn": "鱼骨", "category": 0},

    # 可回收物 (Recyclable) - category 1
    14: {"name": "Recyclable/Battery Pack", "name_cn": "电池组", "category": 1},
    15: {"name": "Recyclable/Bags", "name_cn": "背包", "category": 1},
    16: {"name": "Recyclable/Cosmetic Bottles", "name_cn": "化妆品瓶", "category": 1},
    17: {"name": "Recyclable/Plastic Toys", "name_cn": "塑料玩具", "category": 1},
    18: {"name": "Recyclable/Plastic Bowls and Plates", "name_cn": "塑料碗盘/餐盒", "category": 1},
    19: {"name": "Recyclable/Plastic Hangers", "name_cn": "塑料衣架", "category": 1},
    20: {"name": "Recyclable/Express Paper Bags", "name_cn": "快递纸袋", "category": 1},
    21: {"name": "Recyclable/Plugs and Wires", "name_cn": "插头和电线", "category": 1},
    22: {"name": "Recyclable/Old Clothes", "name_cn": "旧衣服", "category": 1},
    23: {"name": "Recyclable/Aluminum Cans", "name_cn": "铝罐/易拉罐", "category": 1},
    24: {"name": "Recyclable/Pillows", "name_cn": "枕头", "category": 1},
    25: {"name": "Recyclable/Stuffed Toys", "name_cn": "毛绒玩具", "category": 1},
    26: {"name": "Recyclable/Shampoo Bottles", "name_cn": "洗发水瓶", "category": 1},
    27: {"name": "Recyclable/Glass Cups", "name_cn": "玻璃杯", "category": 1},
    28: {"name": "Recyclable/Leather Shoes", "name_cn": "皮鞋", "category": 1},
    29: {"name": "Recyclable/Cutting Boards", "name_cn": "砧板", "category": 1},
    30: {"name": "Recyclable/Cardboard Boxes", "name_cn": "纸板箱", "category": 1},
    31: {"name": "Recyclable/Seasoning Bottles", "name_cn": "调料瓶", "category": 1},
    32: {"name": "Recyclable/Wine Bottles", "name_cn": "酒瓶", "category": 1},
    33: {"name": "Recyclable/Metal Food Cans", "name_cn": "金属食品罐", "category": 1},
    34: {"name": "Recyclable/Pots", "name_cn": "锅", "category": 1},
    35: {"name": "Recyclable/Cooking Oil Containers", "name_cn": "食用油容器", "category": 1},
    36: {"name": "Recyclable/Drink Bottles", "name_cn": "饮料瓶/塑料瓶", "category": 1},
    37: {"name": "Hazardous Waste/Dry Batteries", "name_cn": "干电池", "category": 3},
    38: {"name": "Hazardous Waste/Ointments", "name_cn": "药膏", "category": 3},
    39: {"name": "Recyclable/Paper", "name_cn": "纸张", "category": 1},
}

# COCO 80类 → 中国4类垃圾映射
COCO_TO_WASTE = {
    # 可回收物 - 容器类
    39: {"name": "bottle", "name_cn": "塑料瓶/饮料瓶", "category": 1},
    40: {"name": "wine glass", "name_cn": "玻璃杯", "category": 1},
    41: {"name": "cup", "name_cn": "杯子/塑料杯", "category": 1},
    42: {"name": "fork", "name_cn": "叉子（金属）", "category": 1},
    43: {"name": "knife", "name_cn": "刀具（金属）", "category": 1},
    44: {"name": "spoon", "name_cn": "勺子（金属/塑料）", "category": 1},
    45: {"name": "bowl", "name_cn": "碗/塑料餐盒", "category": 1},

    # 厨余垃圾 - 食物类
    46: {"name": "banana", "name_cn": "香蕉/果皮", "category": 0},
    47: {"name": "apple", "name_cn": "苹果/果核", "category": 0},
    48: {"name": "sandwich", "name_cn": "三明治/食物残渣", "category": 0},
    49: {"name": "orange", "name_cn": "橙子/水果", "category": 0},
    50: {"name": "broccoli", "name_cn": "西兰花/蔬菜", "category": 0},
    51: {"name": "carrot", "name_cn": "胡萝卜/蔬菜", "category": 0},
    52: {"name": "hot dog", "name_cn": "热狗/食物残渣", "category": 0},
    53: {"name": "pizza", "name_cn": "披萨/食物残渣", "category": 0},
    54: {"name": "donut", "name_cn": "甜甜圈/食物残渣", "category": 0},
    55: {"name": "cake", "name_cn": "蛋糕/食物残渣", "category": 0},

    # 可回收物 - 纸张书籍类
    73: {"name": "book", "name_cn": "书本/纸张", "category": 1},
    75: {"name": "vase", "name_cn": "花瓶（玻璃/陶瓷）", "category": 1},
    76: {"name": "scissors", "name_cn": "剪刀（金属）", "category": 1},

    # 可回收物 - 电子设备类
    63: {"name": "laptop", "name_cn": "笔记本电脑（可回收）", "category": 1},
    64: {"name": "mouse", "name_cn": "鼠标（电子垃圾）", "category": 3},
    65: {"name": "remote", "name_cn": "遥控器（电子垃圾）", "category": 3},
    66: {"name": "keyboard", "name_cn": "键盘（电子垃圾）", "category": 3},
    67: {"name": "cell phone", "name_cn": "手机（有害垃圾）", "category": 3},
    70: {"name": "toilet", "name_cn": "马桶（其他垃圾）", "category": 2},
    72: {"name": "clock", "name_cn": "时钟（其他垃圾）", "category": 2},

    # 大件垃圾
    56: {"name": "chair", "name_cn": "椅子（大件垃圾）", "category": 2},
    57: {"name": "couch", "name_cn": "沙发（大件垃圾）", "category": 2},
    59: {"name": "bed", "name_cn": "床（大件垃圾）", "category": 2},
    60: {"name": "dining table", "name_cn": "餐桌（大件垃圾）", "category": 2},

    # 其他COCO类别
    0: {"name": "person", "name_cn": "非垃圾物品", "category": 2},
    1: {"name": "bicycle", "name_cn": "自行车（大件可回收）", "category": 1},
    2: {"name": "car", "name_cn": "汽车（非生活垃圾）", "category": 2},
    3: {"name": "motorcycle", "name_cn": "摩托车（非生活垃圾）", "category": 2},
    4: {"name": "airplane", "name_cn": "飞机（非生活垃圾）", "category": 2},
    5: {"name": "bus", "name_cn": "公交车（非生活垃圾）", "category": 2},
    6: {"name": "train", "name_cn": "火车（非生活垃圾）", "category": 2},
    7: {"name": "truck", "name_cn": "卡车（非生活垃圾）", "category": 2},
    8: {"name": "boat", "name_cn": "船（非生活垃圾）", "category": 2},
    9: {"name": "traffic light", "name_cn": "交通灯（非生活垃圾）", "category": 2},
    10: {"name": "fire hydrant", "name_cn": "消防栓（非生活垃圾）", "category": 2},
    11: {"name": "stop sign", "name_cn": "停止标志（非生活垃圾）", "category": 2},
    12: {"name": "parking meter", "name_cn": "停车计费器（非生活垃圾）", "category": 2},
    13: {"name": "bench", "name_cn": "长椅（大件垃圾）", "category": 2},
    14: {"name": "bird", "name_cn": "鸟类（非垃圾）", "category": 2},
    15: {"name": "cat", "name_cn": "猫（非垃圾）", "category": 2},
    16: {"name": "dog", "name_cn": "狗（非垃圾）", "category": 2},
    17: {"name": "horse", "name_cn": "马（非垃圾）", "category": 2},
    18: {"name": "sheep", "name_cn": "羊（非垃圾）", "category": 2},
    19: {"name": "cow", "name_cn": "牛（非垃圾）", "category": 2},
    20: {"name": "elephant", "name_cn": "大象（非垃圾）", "category": 2},
    21: {"name": "bear", "name_cn": "熊（非垃圾）", "category": 2},
    22: {"name": "zebra", "name_cn": "斑马（非垃圾）", "category": 2},
    23: {"name": "giraffe", "name_cn": "长颈鹿（非垃圾）", "category": 2},
    24: {"name": "backpack", "name_cn": "背包（旧衣物）", "category": 1},
    25: {"name": "umbrella", "name_cn": "雨伞（其他垃圾）", "category": 2},
    26: {"name": "handbag", "name_cn": "手提包（旧衣物）", "category": 1},
    27: {"name": "tie", "name_cn": "领带（旧衣物）", "category": 1},
    28: {"name": "suitcase", "name_cn": "行李箱（其他垃圾）", "category": 2},
    29: {"name": "frisbee", "name_cn": "飞盘（塑料可回收）", "category": 1},
    30: {"name": "skis", "name_cn": "滑雪板（其他垃圾）", "category": 2},
    31: {"name": "snowboard", "name_cn": "滑雪板（其他垃圾）", "category": 2},
    32: {"name": "sports ball", "name_cn": "球类（其他垃圾）", "category": 2},
    33: {"name": "kite", "name_cn": "风筝（其他垃圾）", "category": 2},
    34: {"name": "baseball bat", "name_cn": "棒球棒（其他垃圾）", "category": 2},
    35: {"name": "baseball glove", "name_cn": "棒球手套（其他垃圾）", "category": 2},
    36: {"name": "skateboard", "name_cn": "滑板（其他垃圾）", "category": 2},
    37: {"name": "surfboard", "name_cn": "冲浪板（其他垃圾）", "category": 2},
    38: {"name": "tennis racket", "name_cn": "网球拍（其他垃圾）", "category": 2},
    58: {"name": "potted plant", "name_cn": "盆栽（厨余+其他）", "category": 0},
    61: {"name": "tv", "name_cn": "电视（电子垃圾）", "category": 3},
    62: {"name": "laptop", "name_cn": "笔记本电脑（电子垃圾）", "category": 3},
    68: {"name": "microwave", "name_cn": "微波炉（电子垃圾）", "category": 3},
    69: {"name": "oven", "name_cn": "烤箱（大件垃圾）", "category": 2},
    71: {"name": "sink", "name_cn": "水槽（建筑垃圾）", "category": 2},
    74: {"name": "teddy bear", "name_cn": "泰迪熊（旧衣物）", "category": 1},
    77: {"name": "hair drier", "name_cn": "吹风机（电子垃圾）", "category": 3},
    78: {"name": "toothbrush", "name_cn": "牙刷（其他垃圾）", "category": 2},
    79: {"name": "hair brush", "name_cn": "梳子（其他垃圾）", "category": 2},
}

# 关键词匹配
RECYCLABLE_KEYWORDS = ["塑料", "瓶", "罐", "纸", "纸箱", "书", "报纸", "玻璃", "金属", "铝", "易拉罐", "饮料瓶", "矿泉水瓶", "洗发水", "沐浴露"]
FOOD_WASTE_KEYWORDS = ["果皮", "菜叶", "剩饭", "剩菜", "骨头", "蛋壳", "茶叶", "咖啡渣", "果核", "食物残渣", "厨余", "腐烂"]
HAZARDOUS_KEYWORDS = ["电池", "灯管", "药品", "油漆", "农药", "化学品", "温度计", "血压计", "充电宝", "荧光灯"]
