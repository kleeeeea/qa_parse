import os

from exam_formats import PRAXIS_READING, ExamFormat


class Stage:
    """幂等的流水线步骤的公共骨架。

    run() 负责所有步骤共有的样板逻辑：推导输出路径 → 输出已存在则跳过
    → 建好输出目录 → 调用子类的 _produce() 真正干活 → 返回输出路径
    （各步返回的路径作为下一步的输入，输出已存在即跳过 = 幂等）。

    子类需要：
      - 设 output_basename（输出文件名，放在第一个输入的同目录下），
        或直接重写 derive_output_path() 自定义路径推导；
      - 实现 _produce(output_path, *inputs)：读入、计算、写出、打印汇总。
    """

    output_basename: str = None

    def __init__(self, exam_format: ExamFormat = PRAXIS_READING, skip_if_output_exists=True):
        self.exam_format = exam_format
        self.skip_if_output_exists = skip_if_output_exists

    def derive_output_path(self, *inputs) -> str:
        # 默认：输出文件名放在第一个输入所在目录（全部 5 步都符合这一约定，
        # 包括 join 这种双输入步骤——它按题目侧 csv 的目录定位输出）
        return os.path.join(
            os.path.dirname(os.path.abspath(inputs[0])),
            self.output_basename)

    def _produce(self, output_path: str, *inputs) -> None:
        raise NotImplementedError

    def run(self, *inputs) -> str:
        output_path = self.derive_output_path(*inputs)
        if self.skip_if_output_exists and os.path.exists(output_path):
            print(f'skip: {output_path} already exists')
            return output_path
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        self._produce(output_path, *inputs)
        return output_path
