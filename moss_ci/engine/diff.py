from moss_ci.models.result import PipelineResult, DiffResult, DiffItem


class DiffEngine:
    def compare(self, current: PipelineResult, previous: PipelineResult, score_threshold: float = 0.5) -> DiffResult:
        diff = DiffResult(run_id=current.run_id, previous_run_id=previous.run_id)
        prev_tests = self._index_tests(previous)
        curr_tests = self._index_tests(current)
        for name, cur_test in curr_tests.items():
            prev_test = prev_tests.get(name)
            if prev_test is None:
                continue
            if prev_test.status == "pass" and cur_test.status == "fail":
                diff.new_failures.append(DiffItem(test_name=name, change="new_failure",
                    previous_status=prev_test.status, current_status=cur_test.status))
            elif prev_test.status == "fail" and cur_test.status == "pass":
                diff.fixed.append(DiffItem(test_name=name, change="fixed",
                    previous_status=prev_test.status, current_status=cur_test.status))
            prev_score = self._get_llm_judge_score(prev_test)
            cur_score = self._get_llm_judge_score(cur_test)
            if prev_score is not None and cur_score is not None:
                if cur_score > prev_score + score_threshold:
                    diff.improved.append(DiffItem(test_name=name, change="improved",
                        previous_score=prev_score, current_score=cur_score))
                elif cur_score < prev_score - score_threshold:
                    diff.degraded.append(DiffItem(test_name=name, change="degraded",
                        previous_score=prev_score, current_score=cur_score))
        return diff

    def _index_tests(self, result: PipelineResult) -> dict:
        index = {}
        for suite in result.suites:
            for test in suite.tests:
                index[test.test_name] = test
        return index

    def _get_llm_judge_score(self, test):
        for ev in test.evals:
            if ev.type == "llm_judge" and ev.score is not None:
                return ev.score
        return None
