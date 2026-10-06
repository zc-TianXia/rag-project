import json
import time
import statistics
from pathlib import Path

from django.core.management.base import BaseCommand

from documents.models import DocumentChunk
from documents.services import RAGIngestionService


class Command(BaseCommand):
    """
    RAG 检索评测命令

    用法：
        python manage.py evaluate --create-sample
        python manage.py evaluate --top-k 5
        python manage.py evaluate --top-k 5 --output report.json
    """

    help = "RAG 检索效果评测：对比向量检索、关键词检索、混合检索"

    def add_arguments(self, parser):
        """
        定义命令行参数
        """
        parser.add_argument(
            "--top-k",
            type=int,
            default=5,
            help="检索返回的文档数量，默认 5"
        )
        parser.add_argument(
            "--create-sample",
            action="store_true",
            help="生成测试集模板 test_questions.json"
        )
        parser.add_argument(
            "--test-file",
            type=str,
            default="test_questions.json",
            help="测试集文件路径，默认 test_questions.json"
        )
        parser.add_argument(
            "--output",
            type=str,
            default="",
            help="评测报告输出路径，默认不输出"
        )

    def handle(self, *args, **options):
        """
        命令主入口
        """
        top_k = options["top_k"]
        test_file = options["test_file"]

        # 如果用户要求生成测试集模板
        if options["create_sample"]:
            self.create_sample_file()
            return

        # 检查测试集文件是否存在
        if not Path(test_file).exists():
            self.stderr.write(
                self.style.ERROR(
                    f"测试集文件 {test_file} 不存在，请先运行 --create-sample 生成模板"
                )
            )
            return

        # 加载测试集
        test_questions = self.load_test_questions(test_file)
        if not test_questions:
            self.stderr.write(self.style.ERROR("测试集为空，请检查文件内容"))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"加载 {len(test_questions)} 条测试问题，top_k={top_k}"
            )
        )

        # 执行评测
        results = self.run_evaluation(test_questions, top_k)

        # 输出结果
        self.print_results(results)

        # 可选：导出报告
        if options["output"]:
            self.export_report(results, options["output"])

    def create_sample_file(self):
        """
        生成测试集模板文件
        """
        sample = [
            {
                "question": "示例问题1：请描述你的问题",
                "expected_chunk_ids": [1, 2, 3]
            },
            {
                "question": "示例问题2：请描述你的问题",
                "expected_chunk_ids": [4, 5]
            }
        ]

        file_path = Path("test_questions.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(sample, f, ensure_ascii=False, indent=2)

        self.stdout.write(
            self.style.SUCCESS(f"测试集模板已生成：{file_path}")
        )
        self.stdout.write(
            "请编辑该文件，将 expected_chunk_ids 替换为真实的文档切片 ID"
        )

    def load_test_questions(self, test_file):
        """
        加载测试集文件
        """
        try:
            with open(test_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            self.stderr.write(self.style.ERROR(f"JSON 解析失败：{e}"))
            return []

    def run_evaluation(self, test_questions, top_k):
        """
        对每条测试问题执行三种检索策略并统计结果
        """
        # 直接实例化你的单例类（你的代码里 __new__ 已经实现了单例）
        rag_service = RAGIngestionService()

        # 初始化统计容器
        results = {
            "vector": {"times": [], "recalls": {}},
            "keyword": {"times": [], "recalls": {}},
            "hybrid": {"times": [], "recalls": {}}
        }

        for i, item in enumerate(test_questions, 1):
            question = item["question"]
            expected_ids = set(item["expected_chunk_ids"])

            self.stdout.write(
                f"[{i}/{len(test_questions)}] 问题：{question[:50]}..."
            )

            # 1. 向量检索（你的 search_knowledge 返回 list[dict]，每个 dict 有 'id'）
            vector_start = time.time()
            vector_chunks = rag_service.search_knowledge(
                question, top_k=top_k, use_cache=False
            )
            vector_time = time.time() - vector_start
            vector_ids = [c["id"] for c in vector_chunks]

            # 2. 关键词检索（你的 keyword_search 返回 list[dict]，每个 dict 有 'id'）
            keyword_start = time.time()
            keyword_chunks = rag_service.keyword_search(question, top_k=top_k)
            keyword_time = time.time() - keyword_start
            keyword_ids = [c["id"] for c in keyword_chunks]

            # 3. 混合检索（你的 hybrid_search 返回 list[dict]，每个 dict 有 'id'）
            hybrid_start = time.time()
            hybrid_chunks = rag_service.hybrid_search(question, top_k=top_k, vector_chunks=vector_chunks)
            hybrid_time = time.time() - hybrid_start
            hybrid_ids = [c["id"] for c in hybrid_chunks]

            # 记录耗时
            results["vector"]["times"].append(vector_time)
            results["keyword"]["times"].append(keyword_time)
            results["hybrid"]["times"].append(hybrid_time)

            # 计算 Recall@k
            self.calculate_recall(results["vector"], vector_ids, expected_ids, top_k)
            self.calculate_recall(results["keyword"], keyword_ids, expected_ids, top_k)
            self.calculate_recall(results["hybrid"], hybrid_ids, expected_ids, top_k)

        return results

    def calculate_recall(self, strategy_result, retrieved_ids, expected_ids, top_k):
        """
        计算 Recall@k
        """
        for k in [1, 3, 5]:
            if k <= len(retrieved_ids):
                hits = len(set(retrieved_ids[:k]) & expected_ids)
                recall = hits / len(expected_ids) if expected_ids else 0
                strategy_result["recalls"].setdefault(k, []).append(recall)

    def print_results(self, results):
        """
        打印评测结果对比表
        """
        strategies = {
            "vector": "向量检索",
            "keyword": "关键词检索",
            "hybrid": "混合检索"
        }

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("评测结果对比")
        self.stdout.write("=" * 70)

        # 表头
        header = f"{'策略':<12} {'平均耗时(ms)':<15}"
        for k in [1, 3, 5]:
            header += f" {'Recall@' + str(k):<12}"
        self.stdout.write(header)
        self.stdout.write("-" * 70)

        # 每行数据
        for key, name in strategies.items():
            data = results[key]
            avg_time = statistics.mean(data["times"]) * 1000

            row = f"{name:<12} {avg_time:<15.2f}"
            for k in [1, 3, 5]:
                if k in data["recalls"] and data["recalls"][k]:
                    avg_recall = statistics.mean(data["recalls"][k])
                    row += f" {avg_recall:<12.3f}"
                else:
                    row += f" {'N/A':<12}"
            self.stdout.write(row)

        self.stdout.write("=" * 70)

    def export_report(self, results, output_path):
        """
        导出评测报告到 JSON 文件
        """
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "results": {}
        }

        for key, data in results.items():
            report["results"][key] = {
                "avg_time_ms": statistics.mean(data["times"]) * 1000,
                "avg_recall": {
                    str(k): statistics.mean(v)
                    for k, v in data["recalls"].items()
                    if v
                }
            }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        self.stdout.write(
            self.style.SUCCESS(f"评测报告已导出：{output_path}")
        )
