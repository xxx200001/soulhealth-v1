"""健康管理知识与规则库（V1 有限范围、可审核、可扩展 —— 方案书 §22.4）。

三张表：
  GOALS        健康管理目标（由 assessment 的 goal_tags 指向）
  FOOD_POOLS   目标 → 四类食物池（推荐吃/可以吃/少吃/建议避免），每项含
               面向该用户的理由、建议份量与频率（F-DIET-02/03）
  RECIPES      目标 → 具体菜谱：食材克数、完整步骤、份量、频率、烹饪方式、
               不推荐做法（F-DIET-04 / AC-12）
  TEA_FORMULAS 目标 → 药食同源茶饮：原料克数、水量、制作、频率、周期、
               依据、禁忌（F-TEA-01）。原料仅取自国家药食同源目录常见品种，
               每种原料单列禁忌供 Safety Engine 使用（F-TEA-05：规则不
               硬编码在 LLM 提示词中，本文件即可被规则服务替换）。

内容定位：健康管理层面的膳食参考，非治疗方案；克数为家庭常用量参考。
"""
from __future__ import annotations

GOALS: dict[str, dict] = {
    "liver_care":   {"label": "肝脏健康管理", "why": "肝功能指标偏高或存在脂肪肝相关提示"},
    "lipid_care":   {"label": "血脂管理",     "why": "血脂谱（胆固醇/甘油三酯等）存在异常"},
    "glucose_care": {"label": "血糖管理",     "why": "血糖或糖化血红蛋白高于参考范围"},
    "uric_care":    {"label": "尿酸管理",     "why": "血尿酸偏高"},
    "weight_care":  {"label": "体重管理",     "why": "BMI 超出健康范围"},
    "bp_care":      {"label": "血压管理",     "why": "血压记录偏高"},
    "kidney_care":  {"label": "肾功能关注",   "why": "肾功能相关指标异常"},
    "blood_care":   {"label": "血常规关注",   "why": "血常规存在异常（如血红蛋白偏低）"},
    "general_balance": {"label": "均衡养护",  "why": "当前指标总体平稳，以维持均衡为主"},
}

# ---------------------------------------------------------------- 食物池
# 每项：{name, why, portion, frequency}
FOOD_POOLS: dict[str, dict] = {
    "liver_care": {
        "recommended": [
            {"name": "清蒸鲈鱼/鲳鱼", "why": "优质蛋白帮助肝细胞修复，脂肪含量低",
             "portion": "每次 100–150g", "frequency": "每周 2–3 次"},
            {"name": "西兰花/羽衣甘蓝", "why": "十字花科蔬菜，支持肝脏代谢负担较轻的饮食结构",
             "portion": "每次 150–200g", "frequency": "每日 1 次"},
            {"name": "燕麦", "why": "β-葡聚糖有助于控制总能量与血脂，减轻肝脏脂肪来源",
             "portion": "干重 40–50g", "frequency": "每日早餐"},
            {"name": "豆腐/豆制品", "why": "以植物蛋白替代部分红肉，降低饱和脂肪摄入",
             "portion": "每次 100g", "frequency": "每周 3–4 次"},
        ],
        "allowed": [
            {"name": "鸡胸肉、去皮禽肉", "why": "低脂蛋白来源，注意去皮少油"},
            {"name": "鸡蛋", "why": "每日 1 个整蛋一般可接受"},
            {"name": "低脂酸奶", "why": "选无糖款，兼顾蛋白与肠道"},
        ],
        "limit": [
            {"name": "红肉（猪牛羊）", "why": "饱和脂肪偏高，加重肝脏脂质负担",
             "portion": "每周合计不超过 300g"},
            {"name": "精制主食（白米白面）", "why": "过量转化为肝脏脂肪合成原料，建议 1/3 换成全谷杂粮"},
            {"name": "坚果", "why": "健康脂肪但能量密度高，每日一小把（约 15g）为限"},
        ],
        "avoid": [
            {"name": "酒精（各类酒）", "why": "肝功能异常期间应严格避免，酒精直接加重肝细胞损伤"},
            {"name": "油炸食品", "why": "高温油脂显著增加肝脏代谢负担"},
            {"name": "含糖饮料/果汁饮料", "why": "果糖过量是脂肪肝的重要膳食因素"},
            {"name": "动物内脏、肥肉", "why": "高脂高胆固醇，不利于肝脂管理"},
        ],
    },
    "lipid_care": {
        "recommended": [
            {"name": "深海鱼（三文鱼/鲭鱼/沙丁鱼）", "why": "富含 Omega-3，有助于甘油三酯管理",
             "portion": "每次 100–150g", "frequency": "每周 2 次"},
            {"name": "燕麦/糙米等全谷物", "why": "可溶性膳食纤维帮助控制胆固醇吸收",
             "portion": "替代一半精制主食", "frequency": "每日"},
            {"name": "深色绿叶菜", "why": "膳食纤维与植物固醇丰富、能量低",
             "portion": "每日 300–500g 蔬菜其中一半深色", "frequency": "每日"},
            {"name": "原味坚果（核桃/杏仁）", "why": "不饱和脂肪替代饱和脂肪",
             "portion": "每日 10–15g", "frequency": "每日一小把"},
        ],
        "allowed": [
            {"name": "去皮禽肉、瘦肉", "why": "控制在每日 50–75g"},
            {"name": "鸡蛋", "why": "一般人群每日 1 个可接受"},
            {"name": "橄榄油/茶籽油烹调", "why": "以单不饱和脂肪替代动物油"},
        ],
        "limit": [
            {"name": "红肉与加工肉", "why": "饱和脂肪来源，红肉每周不超过 300g，加工肉尽量少"},
            {"name": "全脂乳制品", "why": "可换低脂/脱脂"},
            {"name": "椰子油、棕榈油制品", "why": "植物来源但饱和脂肪高"},
        ],
        "avoid": [
            {"name": "反式脂肪（人造奶油、起酥点心、植脂末）", "why": "明确升高低密度脂蛋白"},
            {"name": "油炸食品", "why": "高能量高氧化油脂"},
            {"name": "动物内脏、蟹黄鱼籽", "why": "胆固醇密度高"},
        ],
    },
    "glucose_care": {
        "recommended": [
            {"name": "杂豆与全谷物（鹰嘴豆/黑米/藜麦）", "why": "低升糖指数主食，餐后血糖更平稳",
             "portion": "替代 1/2 精制主食", "frequency": "每餐"},
            {"name": "绿叶蔬菜与瓜茄类", "why": "膳食纤维延缓糖吸收，能量低",
             "portion": "每餐先吃 150g 以上", "frequency": "每餐"},
            {"name": "清蒸鱼、去皮禽肉", "why": "优质蛋白增强饱腹、稳定餐后血糖",
             "portion": "每餐掌心大小", "frequency": "每日"},
        ],
        "allowed": [
            {"name": "低糖水果（草莓/蓝莓/柚子）", "why": "两餐之间食用，每次 150g 内"},
            {"name": "无糖酸奶", "why": "加餐替代甜食"},
        ],
        "limit": [
            {"name": "白米白面等精制主食", "why": "建议至少一半换成全谷杂豆"},
            {"name": "高糖水果（荔枝/龙眼/榴莲/熟香蕉）", "why": "偶尔少量，避免空腹大量"},
            {"name": "根茎类淀粉（土豆/山药/藕）", "why": "计入主食总量，不作为蔬菜加量"},
        ],
        "avoid": [
            {"name": "含糖饮料、奶茶、果汁", "why": "液态糖吸收快，血糖波动最大"},
            {"name": "糕点糖果、蜂蜜冲调", "why": "添加糖直接推高血糖"},
            {"name": "白粥、糊化过度主食", "why": "升糖速度接近直接摄糖"},
        ],
    },
    "uric_care": {
        "recommended": [
            {"name": "低脂乳制品（牛奶/酸奶）", "why": "研究提示有助于尿酸排泄",
             "portion": "每日 300ml", "frequency": "每日"},
            {"name": "新鲜蔬菜", "why": "碱化尿液、低嘌呤",
             "portion": "每日 500g", "frequency": "每日"},
            {"name": "足量饮水", "why": "促进尿酸经肾排出",
             "portion": "每日 2000ml 以上（心肾功能正常前提）", "frequency": "全天分次"},
            {"name": "鸡蛋", "why": "低嘌呤优质蛋白来源", "portion": "每日 1 个", "frequency": "每日"},
        ],
        "allowed": [
            {"name": "淡水鱼、去皮禽肉", "why": "中嘌呤，急性不适期外可适量，每次 ≤100g"},
            {"name": "豆腐等豆制品", "why": "加工后嘌呤降低，一般人群可适量"},
            {"name": "咖啡（不加糖）", "why": "多数研究未提示升尿酸"},
        ],
        "limit": [
            {"name": "红肉", "why": "中高嘌呤且饱和脂肪高，每周不超过 2 次"},
            {"name": "菌菇、芦笋、紫菜", "why": "植物中嘌呤偏高者，控制频次即可"},
        ],
        "avoid": [
            {"name": "动物内脏", "why": "嘌呤密度最高的一类食物"},
            {"name": "浓肉汤、火锅汤底", "why": "嘌呤溶于汤中，浓汤=高嘌呤"},
            {"name": "啤酒及各类酒精", "why": "酒精抑制尿酸排泄，啤酒同时含高嘌呤"},
            {"name": "海鲜贝类（沙丁鱼/凤尾鱼/牡蛎等）", "why": "高嘌呤海产"},
            {"name": "含果糖饮料", "why": "果糖代谢直接升高尿酸"},
        ],
    },
    "weight_care": {
        "recommended": [
            {"name": "高纤蔬菜打底", "why": "先菜后饭，降低整体能量密度",
             "portion": "每餐 200g 起", "frequency": "每餐"},
            {"name": "优质蛋白（鱼/禽/豆/蛋）", "why": "保住肌肉、提升饱腹",
             "portion": "每餐掌心大小", "frequency": "每餐"},
            {"name": "全谷物主食", "why": "同等能量下饱腹更久",
             "portion": "每餐拳头大小", "frequency": "每餐"},
        ],
        "allowed": [
            {"name": "水果", "why": "每日 200–350g，放两餐之间"},
            {"name": "原味坚果", "why": "每日一小把 10g 内"},
        ],
        "limit": [
            {"name": "外卖高油菜品", "why": "点单备注少油，优先蒸煮"},
            {"name": "精制主食", "why": "减量 1/4 并部分换粗粮"},
        ],
        "avoid": [
            {"name": "含糖饮料与酒精", "why": "液态能量最易过量"},
            {"name": "油炸与酥皮点心", "why": "能量密度最高的一类"},
        ],
    },
    "bp_care": {
        "recommended": [
            {"name": "高钾蔬果（菠菜/香蕉/猕猴桃）", "why": "钾有助于钠的排出与血压管理",
             "portion": "蔬菜每日 500g、水果 200–350g", "frequency": "每日"},
            {"name": "低脂乳制品", "why": "DASH 饮食核心组成", "portion": "每日 300ml",
             "frequency": "每日"},
            {"name": "全谷物", "why": "替代精制主食，配合体重管理", "portion": "每餐一半",
             "frequency": "每日"},
        ],
        "allowed": [
            {"name": "鱼禽瘦肉", "why": "每日 100–150g"},
            {"name": "原味坚果", "why": "每日一小把"},
        ],
        "limit": [
            {"name": "酱油、蚝油、豆瓣酱等调味", "why": "隐形钠大户，做菜后放、减半用"},
            {"name": "腌制小菜", "why": "偶尔佐餐，不作日常"},
        ],
        "avoid": [
            {"name": "高盐加工食品（火腿/方便面/薯片）", "why": "单份钠即可超每日限量的一半"},
            {"name": "酒精", "why": "直接升压因素"},
        ],
    },
    "kidney_care": {
        "recommended": [
            {"name": "新鲜蔬菜（焯水后食用）", "why": "焯水减钾，减轻肾脏负担的前提下保证纤维",
             "portion": "每日 300–500g", "frequency": "每日"},
            {"name": "适量优质蛋白（蛋清/鱼/瘦肉）", "why": "优先优质蛋白、控制总量",
             "portion": "遵医嘱调整，一般每公斤体重 0.8g 左右", "frequency": "每日"},
        ],
        "allowed": [
            {"name": "低钾水果（苹果/梨/葡萄）", "why": "每日 200g 内"},
        ],
        "limit": [
            {"name": "豆类及坚果", "why": "磷与钾偏高，肾功能异常时控制频次"},
            {"name": "汤类", "why": "肉汤含钾磷较高，少喝汤多吃肉"},
        ],
        "avoid": [
            {"name": "腌制高盐食品", "why": "钠负荷直接加重肾脏工作量"},
            {"name": "杨桃", "why": "肾功能不全者存在明确神经毒性风险"},
            {"name": "浓茶浓汤、加工肉", "why": "高磷高钠"},
        ],
    },
    "blood_care": {
        "recommended": [
            {"name": "红肉瘦肉/动物血/肝脏（适量）", "why": "血红素铁吸收率高，适合血红蛋白偏低者",
             "portion": "瘦肉每日 50–75g，肝脏每周 1 次 25g", "frequency": "见份量"},
            {"name": "维生素C水果（橙/猕猴桃）配餐", "why": "同餐维C可显著促进铁吸收",
             "portion": "每餐后 100g", "frequency": "每日"},
            {"name": "深绿叶菜", "why": "补充叶酸", "portion": "每日 200g", "frequency": "每日"},
        ],
        "allowed": [
            {"name": "蛋类、豆制品", "why": "蛋白与微量元素补充"},
        ],
        "limit": [
            {"name": "浓茶咖啡", "why": "鞣酸抑制铁吸收，与正餐隔开 1 小时以上"},
        ],
        "avoid": [
            {"name": "以零食替代正餐", "why": "能量够但造血原料不足"},
        ],
    },
    "general_balance": {
        "recommended": [
            {"name": "多彩蔬菜", "why": "每日 300–500g、种类过 5 种",
             "portion": "每餐一半盘面", "frequency": "每日"},
            {"name": "全谷物与杂豆", "why": "主食的 1/3 以上", "portion": "每餐拳头大小",
             "frequency": "每日"},
            {"name": "鱼禽蛋奶豆轮换", "why": "蛋白来源多样化", "portion": "每餐掌心大小",
             "frequency": "每日"},
        ],
        "allowed": [
            {"name": "水果", "why": "每日 200–350g"},
            {"name": "原味坚果", "why": "每日一小把"},
        ],
        "limit": [
            {"name": "添加糖", "why": "每日不超过 25g"},
            {"name": "烹调油", "why": "每日 25–30g"},
        ],
        "avoid": [
            {"name": "长期依赖外卖高油高盐", "why": "隐形油盐糖是慢病主要膳食来源"},
        ],
    },
}

# ---------------------------------------------------------------- 菜谱
RECIPES: dict[str, list] = {
    "liver_care": [
        {"name": "清蒸鲈鱼配姜丝",
         "reason": "低脂高蛋白的经典做法，帮助肝细胞修复且不增加脂质负担",
         "ingredients": [{"name": "鲈鱼", "grams": 400, "note": "约一条"},
                         {"name": "生姜", "grams": 10, "note": "切细丝"},
                         {"name": "小葱", "grams": 10}, {"name": "蒸鱼豉油", "grams": 10},
                         {"name": "植物油", "grams": 5}],
         "steps": ["鲈鱼洗净两面各划两刀，鱼身抹少量姜丝去腥，静置 10 分钟",
                   "盘底垫葱段，水开后上锅大火蒸 8–9 分钟（筷子能轻松插入鱼背最厚处即熟）",
                   "倒掉盘中腥水，铺新姜丝葱丝，淋 10g 蒸鱼豉油",
                   "5g 植物油烧热浇在葱姜丝上激香即可"],
         "serving": "2 人份，每人约 150g 鱼肉", "frequency": "每周 2–3 次",
         "cooking_method": "清蒸（大火足汽、控制在 10 分钟内）",
         "avoid_methods": ["油炸", "红烧重油重糖", "煎烤焦化"]},
        {"name": "燕麦蔬菜蛋饼",
         "reason": "全谷物+蔬菜+蛋白的一餐式早餐，替代高油早点",
         "ingredients": [{"name": "即食燕麦", "grams": 40}, {"name": "鸡蛋", "grams": 100,
                          "note": "2 个"}, {"name": "胡萝卜丝", "grams": 50},
                         {"name": "菠菜碎", "grams": 50}, {"name": "植物油", "grams": 5},
                         {"name": "盐", "grams": 1}],
         "steps": ["燕麦加 60ml 温水泡 5 分钟", "拌入鸡蛋、蔬菜与盐搅匀",
                   "不粘锅刷薄油，小火两面各煎 3 分钟至定型金黄"],
         "serving": "1 人份", "frequency": "每周 3–4 次早餐",
         "cooking_method": "少油小火煎",
         "avoid_methods": ["多油煎炸", "加糖调味"]},
    ],
    "lipid_care": [
        {"name": "香煎三文鱼配西兰花",
         "reason": "一餐同时获得 Omega-3 与膳食纤维，替代红肉晚餐",
         "ingredients": [{"name": "三文鱼", "grams": 130}, {"name": "西兰花", "grams": 200},
                         {"name": "橄榄油", "grams": 8}, {"name": "黑胡椒", "grams": 1},
                         {"name": "柠檬", "grams": 20, "note": "两角挤汁"}],
         "steps": ["西兰花掰小朵沸水焯 2 分钟捞出", "三文鱼两面撒黑胡椒",
                   "不粘锅下橄榄油，中火皮朝下煎 3 分钟，翻面再 2 分钟",
                   "装盘配西兰花，食用前挤柠檬汁"],
         "serving": "1 人份", "frequency": "每周 2 次",
         "cooking_method": "少油中火快煎", "avoid_methods": ["裹粉油炸", "奶油浓酱"]},
        {"name": "杂粮饭（燕麦糙米红豆）",
         "reason": "以可溶性纤维替换一半白米，帮助控制胆固醇吸收",
         "ingredients": [{"name": "糙米", "grams": 50}, {"name": "燕麦米", "grams": 30},
                         {"name": "红豆", "grams": 20}, {"name": "白米", "grams": 50}],
         "steps": ["糙米红豆提前泡 2 小时", "全部混合，水量比白米饭多 1/4",
                   "电饭煲正常煮饭程序即可"],
         "serving": "2 人份主食", "frequency": "每日替代白米饭",
         "cooking_method": "电饭煲蒸煮", "avoid_methods": ["炒饭回锅加油"]},
    ],
    "glucose_care": [
        {"name": "鹰嘴豆时蔬鸡胸沙拉",
         "reason": "低升糖主食+蛋白+纤维的组合，餐后血糖更平稳",
         "ingredients": [{"name": "熟鹰嘴豆", "grams": 80}, {"name": "鸡胸肉", "grams": 100},
                         {"name": "生菜/黄瓜/番茄", "grams": 200},
                         {"name": "橄榄油", "grams": 8}, {"name": "柠檬汁", "grams": 10}],
         "steps": ["鸡胸肉冷水下锅加姜片，小火煮 12 分钟，捞出撕条",
                   "蔬菜洗净切块，与鹰嘴豆、鸡丝混合",
                   "橄榄油+柠檬汁+少许盐调汁拌匀"],
         "serving": "1 人份正餐", "frequency": "每周 3–4 次",
         "cooking_method": "水煮+凉拌", "avoid_methods": ["沙拉酱/千岛酱", "蜜汁调味"]},
        {"name": "清炒双花（西兰花+菜花）",
         "reason": "先吃一盘再动主食，是控制餐后血糖最省事的一步",
         "ingredients": [{"name": "西兰花", "grams": 150}, {"name": "菜花", "grams": 150},
                         {"name": "蒜", "grams": 10}, {"name": "植物油", "grams": 8},
                         {"name": "盐", "grams": 2}],
         "steps": ["双花掰小朵，沸水焯 1 分钟", "热锅下油爆香蒜末",
                   "下双花大火翻炒 2 分钟，加盐出锅"],
         "serving": "2 人份配菜", "frequency": "每日",
         "cooking_method": "焯水+快炒", "avoid_methods": ["勾芡", "糖醋做法"]},
    ],
    "uric_care": [
        {"name": "冬瓜薏白汤（去薏苡仁版）",
         "reason": "高水分低嘌呤汤品，帮助达成每日饮水目标",
         "ingredients": [{"name": "冬瓜", "grams": 400}, {"name": "干贝素/盐", "grams": 2},
                         {"name": "生姜", "grams": 5}, {"name": "小葱", "grams": 5}],
         "steps": ["冬瓜去皮切块", "清水 800ml 加姜片煮沸",
                   "下冬瓜中火煮 10 分钟至透明", "调味撒葱花"],
         "serving": "2 人份", "frequency": "每周 3–4 次",
         "cooking_method": "清水煮（不用肉汤打底）",
         "avoid_methods": ["浓肉汤/骨汤打底", "加啤酒炖"]},
        {"name": "牛奶蒸蛋",
         "reason": "低嘌呤优质蛋白+乳制品，适合尿酸偏高者的蛋白来源",
         "ingredients": [{"name": "鸡蛋", "grams": 100, "note": "2 个"},
                         {"name": "低脂牛奶", "grams": 150}, {"name": "盐", "grams": 1}],
         "steps": ["鸡蛋打散加牛奶与盐，过筛去泡",
                   "覆保鲜膜扎孔，水开后中小火蒸 10 分钟"],
         "serving": "1 人份", "frequency": "每日早餐可选",
         "cooking_method": "隔水蒸", "avoid_methods": ["加虾皮/干贝提鲜（嘌呤高）"]},
    ],
    "weight_care": [
        {"name": "彩椒鸡胸串（烤箱版）",
         "reason": "高蛋白低能量正餐主菜，饱腹不过量",
         "ingredients": [{"name": "鸡胸肉", "grams": 150}, {"name": "彩椒", "grams": 100},
                         {"name": "洋葱", "grams": 50}, {"name": "橄榄油", "grams": 5},
                         {"name": "黑胡椒/盐", "grams": 2}],
         "steps": ["鸡胸切块用盐胡椒腌 15 分钟", "与彩椒洋葱交替穿串刷薄油",
                   "烤箱 200℃ 烤 12–15 分钟"],
         "serving": "1 人份", "frequency": "每周 3 次",
         "cooking_method": "烤箱少油烤", "avoid_methods": ["油炸", "刷蜜汁烤酱"]},
    ],
    "bp_care": [
        {"name": "凉拌菠菜（后放盐）",
         "reason": "高钾蔬菜+起锅后放盐，同一道菜省一半钠",
         "ingredients": [{"name": "菠菜", "grams": 300}, {"name": "蒜末", "grams": 8},
                         {"name": "香油", "grams": 5}, {"name": "盐", "grams": 1.5},
                         {"name": "醋", "grams": 8}],
         "steps": ["菠菜沸水焯 40 秒过凉挤干", "加蒜末香油醋拌匀",
                   "吃前才撒盐拌两下——盐留在表面，用量减半味道不减"],
         "serving": "2 人份", "frequency": "每日一道高钾菜",
         "cooking_method": "焯拌", "avoid_methods": ["咸菜同拌", "加酱油+盐双重钠"]},
    ],
    "kidney_care": [
        {"name": "焯水时蔬蒸蛋白",
         "reason": "焯水减钾 + 蛋白优先取蛋清，肾功能关注期的稳妥搭配",
         "ingredients": [{"name": "蛋清", "grams": 120, "note": "约 3 个蛋的蛋清"},
                         {"name": "西葫芦", "grams": 150}, {"name": "盐", "grams": 1}],
         "steps": ["西葫芦切片沸水焯 1 分钟弃水", "蛋清加 120ml 温水打匀过筛",
                   "铺入蔬菜，水开后中火蒸 8 分钟"],
         "serving": "1 人份", "frequency": "每周 3 次",
         "cooking_method": "焯水+蒸", "avoid_methods": ["浓汤打底", "腌制配菜"]},
    ],
    "blood_care": [
        {"name": "番茄炖牛腩（瘦）",
         "reason": "血红素铁+维C同锅，铁吸收效率高",
         "ingredients": [{"name": "牛腩（瘦）", "grams": 200}, {"name": "番茄", "grams": 300},
                         {"name": "洋葱", "grams": 50}, {"name": "植物油", "grams": 8},
                         {"name": "盐", "grams": 2}],
         "steps": ["牛腩焯水去沫", "番茄去皮切块炒出沙",
                   "加牛腩与热水没过，小火炖 60 分钟至软烂，调味"],
         "serving": "2–3 人份", "frequency": "每周 1–2 次",
         "cooking_method": "小火慢炖", "avoid_methods": ["与浓茶同餐（隔开 1 小时）"]},
    ],
    "general_balance": [
        {"name": "一碗均衡饭（模板）",
         "reason": "把餐盘法变成一碗：一半蔬菜、四分之一全谷、四分之一蛋白",
         "ingredients": [{"name": "杂粮饭", "grams": 120}, {"name": "时令蔬菜两种", "grams": 200},
                         {"name": "鱼/禽/豆任选", "grams": 100}, {"name": "植物油", "grams": 8}],
         "steps": ["蔬菜快炒或焯拌", "蛋白类清蒸/水煮/快煎任选",
                   "按 2:1:1 装碗即为一餐"],
         "serving": "1 人份", "frequency": "每日模板",
         "cooking_method": "蒸煮快炒为主", "avoid_methods": ["油炸", "重酱调味"]},
    ],
}

# ---------------------------------------------------------------- 药食同源茶饮
# 原料级禁忌供 Safety Engine 逐条核对；配方级 contraindications 面向用户展示。
TEA_INGREDIENT_RULES: dict[str, dict] = {
    "山楂":   {"pregnancy_block": True,  "notes": "促宫缩风险，孕妇忌用；胃酸过多/胃溃疡慎用"},
    "决明子": {"pregnancy_block": True,  "notes": "性微寒滑肠，孕妇及脾虚便溏者不宜；低血压者慎用"},
    "薏苡仁": {"pregnancy_block": True,  "notes": "传统认为孕早期慎用；脾胃虚寒者控制用量"},
    "荷叶":   {"pregnancy_block": True,  "notes": "体瘦气血虚弱者与孕妇不宜长期饮用"},
    "菊花":   {"pregnancy_block": False, "notes": "性微寒，脾胃虚寒易腹泻者减量；菊科过敏者禁用"},
    "枸杞子": {"pregnancy_block": False, "notes": "外感发热、腹泻期间暂停"},
    "陈皮":   {"pregnancy_block": False, "notes": "气虚津亏、实热者不宜久用"},
    "茯苓":   {"pregnancy_block": False, "notes": "肾虚多尿者慎用"},
    "桑叶":   {"pregnancy_block": False, "notes": "性寒，脾胃虚寒者减量"},
    "玉竹":   {"pregnancy_block": False, "notes": "痰湿气滞者不宜"},
    "百合":   {"pregnancy_block": False, "notes": "风寒咳嗽及脾虚便溏者慎用"},
    "莲子":   {"pregnancy_block": False, "notes": "大便干结者少用"},
    "酸枣仁": {"pregnancy_block": False, "notes": "有实邪郁火者慎用"},
    "大枣":   {"pregnancy_block": False, "notes": "糖尿病者控制用量（含糖）"},
    "生姜":   {"pregnancy_block": False, "notes": "阴虚内热者少用"},
    "甘草":   {"pregnancy_block": False, "notes": "高血压/水肿者不宜长期，可能引起水钠潴留",
               "bp_caution": True},
}

TEA_FORMULAS: dict[str, dict] = {
    "liver_care": {
        "name": "疏养清和茶", "goal_label": "肝脏健康管理",
        "ingredients": [{"name": "菊花", "grams": 5}, {"name": "枸杞子", "grams": 6},
                        {"name": "陈皮", "grams": 3}],
        "water_ml": 500, "brew": "沸水冲泡，加盖焖 8–10 分钟；可复冲 1 次",
        "frequency": "每日 1 剂，代茶温饮", "cycle": "连续 2 周为一周期，间歇 3–5 天再评估",
        "rationale": "菊花清利头目、枸杞子养肝明目、陈皮理气和中；性味以平和微凉为主，"
                     "适合肝功能指标偏高时的日常养护搭配",
        "contraindications": ["脾胃虚寒、易腹泻者减菊花用量或改隔日饮",
                              "菊科植物过敏者禁用", "感冒发热期间暂停"],
    },
    "lipid_care": {
        "name": "山楂陈皮饮", "goal_label": "血脂管理",
        "ingredients": [{"name": "山楂", "grams": 8, "note": "干片"},
                        {"name": "陈皮", "grams": 3}, {"name": "荷叶", "grams": 3}],
        "water_ml": 600, "brew": "冷水下料煮沸后转小火 10 分钟，滤渣代茶",
        "frequency": "每日 1 剂，餐后温饮", "cycle": "连续 2–4 周，复查血脂后调整",
        "rationale": "山楂消食化积、荷叶升清化浊、陈皮行气，是传统消脂化浊的常用配伍方向",
        "contraindications": ["孕妇忌用（含山楂、荷叶）", "胃酸过多、胃溃疡者慎用",
                              "空腹不饮，避免刺激胃酸"],
    },
    "glucose_care": {
        "name": "桑叶玉竹茶", "goal_label": "血糖管理",
        "ingredients": [{"name": "桑叶", "grams": 5}, {"name": "玉竹", "grams": 6},
                        {"name": "枸杞子", "grams": 5}],
        "water_ml": 500, "brew": "沸水冲泡加盖焖 10 分钟；玉竹可煮 5 分钟风味更佳",
        "frequency": "每日 1 剂", "cycle": "连续 2 周为一周期，配合血糖监测",
        "rationale": "桑叶生津清润、玉竹养阴，为传统「消渴」食养中的平和搭配；"
                     "本茶为膳食辅助，不替代任何降糖治疗",
        "contraindications": ["脾胃虚寒易腹泻者减量", "正在使用降糖药者注意监测血糖，"
                              "如有低血糖表现及时进食并咨询医生"],
    },
    "uric_care": {
        "name": "茯苓薏仁饮", "goal_label": "尿酸管理",
        "ingredients": [{"name": "茯苓", "grams": 8}, {"name": "薏苡仁", "grams": 15,
                        "note": "炒制更平和"}, {"name": "陈皮", "grams": 3}],
        "water_ml": 800, "brew": "薏苡仁先煮 15 分钟，再入茯苓陈皮同煮 10 分钟",
        "frequency": "每日 1 剂，全天分次温饮", "cycle": "连续 2–4 周，配合多饮水",
        "rationale": "茯苓、薏苡仁利水渗湿，陈皮理气，契合「湿浊内蕴」的传统食养方向；"
                     "同时天然增加每日水分摄入",
        "contraindications": ["孕妇忌用（含薏苡仁）", "脾胃虚寒者薏苡仁用炒制并减量",
                              "肾功能不全者饮水量遵医嘱，不盲目加量"],
    },
    "weight_care": {
        "name": "荷叶陈皮茶", "goal_label": "体重管理",
        "ingredients": [{"name": "荷叶", "grams": 4}, {"name": "陈皮", "grams": 3},
                        {"name": "山楂", "grams": 5}],
        "water_ml": 600, "brew": "沸水冲泡加盖焖 10 分钟，可复冲 1 次",
        "frequency": "每日 1 剂，上午或午后饮", "cycle": "连续 2 周为一周期",
        "rationale": "荷叶化浊、山楂消积、陈皮行气，配合饮食控制作为体重管理期的日常茶饮",
        "contraindications": ["孕妇忌用", "体瘦虚弱、气血不足者不宜",
                              "胃酸过多者慎用山楂"],
    },
    "bp_care": {
        "name": "菊花决明茶", "goal_label": "血压管理",
        "ingredients": [{"name": "菊花", "grams": 5}, {"name": "决明子", "grams": 8,
                        "note": "炒制"}, {"name": "枸杞子", "grams": 5}],
        "water_ml": 500, "brew": "决明子略捣，沸水冲泡加盖焖 10 分钟",
        "frequency": "每日 1 剂", "cycle": "连续 2 周为一周期；血压管理以监测与就医为主",
        "rationale": "菊花清肝、决明子清肝明目润肠，为传统平肝方向的温和茶饮；"
                     "茶饮仅为辅助，不能替代任何降压治疗",
        "contraindications": ["孕妇忌用（含决明子）", "脾虚便溏者不宜（决明子滑肠）",
                              "低血压者慎用", "正在服降压药者注意监测，出现头晕及时就医"],
    },
    "kidney_care": {
        "name": "玉竹百合茶", "goal_label": "肾功能关注",
        "ingredients": [{"name": "玉竹", "grams": 6}, {"name": "百合", "grams": 6},
                        {"name": "枸杞子", "grams": 4}],
        "water_ml": 400, "brew": "小火同煮 10 分钟，滤渣温饮",
        "frequency": "每日 1 剂，饮水总量遵医嘱", "cycle": "连续 1–2 周",
        "rationale": "以甘平养阴之品为主的轻量茶饮；肾功能关注期任何草本饮品都应保守，"
                     "本方仅作低负担的日常茶替代",
        "contraindications": ["肾功能不全者须先咨询医生，饮水量个体化",
                              "痰湿盛、便溏者减量"],
    },
    "blood_care": {
        "name": "枣杞桂圆茶", "goal_label": "血常规关注（气血养护）",
        "ingredients": [{"name": "大枣", "grams": 10, "note": "去核 3 枚"},
                        {"name": "枸杞子", "grams": 6}, {"name": "生姜", "grams": 2}],
        "water_ml": 400, "brew": "同煮 8 分钟或沸水焖泡 10 分钟",
        "frequency": "每日 1 剂", "cycle": "连续 2 周",
        "rationale": "大枣、枸杞为传统补益气血的食养常用之品，佐生姜温中",
        "contraindications": ["糖尿病或血糖偏高者减大枣并计入当日糖量",
                              "感冒发热期间暂停", "湿热体质（口苦苔腻）减量"],
    },
    "general_balance": {
        "name": "四季平和茶", "goal_label": "均衡养护",
        "ingredients": [{"name": "枸杞子", "grams": 5}, {"name": "菊花", "grams": 3},
                        {"name": "大枣", "grams": 6, "note": "去核 2 枚"}],
        "water_ml": 450, "brew": "沸水冲泡加盖焖 8 分钟，可复冲",
        "frequency": "每日 1 剂或隔日", "cycle": "四季可饮，随体感调整",
        "rationale": "一凉一温一平的基础搭配，作为日常代茶的均衡选择",
        "contraindications": ["菊科过敏者去菊花", "血糖偏高者减大枣"],
    },
}


def goal_label(tag: str) -> str:
    return GOALS.get(tag, {}).get("label", tag)
