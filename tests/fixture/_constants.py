import os

# 测试数据相对本文件定位（tests/fixture/），不依赖 $HOME 绝对路径，
# 仓库挪动/换机器后仍然有效。
_FIXTURE_DIR = os.path.dirname(os.path.abspath(__file__))

mineruparsed = os.path.join(
    _FIXTURE_DIR,
    'praxis_reading_1',
    'eaa0dd7f-206c-485e-82db-2b4b355ff0a9_origin',
    'full.md',
)

# plt_8：题目和答案是两份单独解析的 PDF（对应 run_pipeline 的双输入）
plt_8_question_mineruparsed = os.path.join(
    _FIXTURE_DIR,
    'plt_8',
    'plt_8_question.pdf-4204cb3f-926f-4802-bb3e-61ea568c66bf',
    'full.md',
)
plt_8_answer_mineruparsed = os.path.join(
    _FIXTURE_DIR,
    'plt_8',
    'plt_8_answer.pdf-305c29d9-85b4-4d18-8c73-577a0b2696a9',
    'full.md',
)
