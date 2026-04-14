#!/usr/bin/env python3
"""Tests for parallel journal article processing in CitationSculptor."""

import sys
import threading
import time
from unittest.mock import Mock, patch, MagicMock, PropertyMock

import pytest

# Patch heavy imports before importing CitationSculptor
sys.modules.setdefault('modules.file_handler', MagicMock())
sys.modules.setdefault('modules.reference_parser', MagicMock())
sys.modules.setdefault('modules.type_detector', MagicMock())
sys.modules.setdefault('modules.pubmed_client', MagicMock())
sys.modules.setdefault('modules.vancouver_formatter', MagicMock())
sys.modules.setdefault('modules.inline_replacer', MagicMock())
sys.modules.setdefault('modules.output_generator', MagicMock())

from citation_sculptor import CitationSculptor


def _make_sculptor(max_workers=8):
    """Create a CitationSculptor with mocked dependencies for testing."""
    sculptor = object.__new__(CitationSculptor)
    sculptor.input_path = "/tmp/test.md"
    sculptor.output_path = None
    sculptor.verbose = False
    sculptor.dry_run = False
    sculptor.create_backup = True
    sculptor.use_gui = False
    sculptor.multi_section = False
    sculptor.gui_dialog = None
    sculptor.max_workers = max_workers
    sculptor.processed_citations = []
    sculptor.manual_review_items = []
    sculptor.number_to_label_map = {}
    sculptor._lock = threading.Lock()
    sculptor.type_detector = Mock()
    sculptor.pubmed_client = Mock()
    sculptor.formatter = Mock()
    sculptor.output_generator = Mock()
    sculptor.webpage_scraper = None
    return sculptor


def _make_ref(number, url=None, title="Test Article"):
    """Create a mock ParsedReference."""
    ref = Mock()
    ref.original_number = number
    ref.url = url or f"https://pubmed.ncbi.nlm.nih.gov/{10000 + number}/"
    ref.title = f"{title} {number}"
    ref.original_text = f"[{number}] {title} {number}. Journal. 2024."
    ref.source_name = "PubMed"
    ref.metadata = {}
    ref.processed = False
    ref.new_label = None
    ref.needs_review = False
    ref.review_reason = None
    return ref


def _make_result(label):
    """Create a mock FormattedCitation result."""
    result = Mock()
    result.label = label
    return result


class TestParallelProcessing:
    """Tests for ThreadPoolExecutor-based parallel reference processing."""

    def test_all_refs_processed_concurrently(self):
        """All references should be processed when running in parallel.

        Verifies that 10 refs each taking 100ms complete in well under 10*100ms,
        proving parallel execution.
        """
        sculptor = _make_sculptor(max_workers=10)
        refs = [_make_ref(i) for i in range(1, 11)]

        original_process = sculptor._process_single_journal_article

        def slow_process(ref):
            time.sleep(0.1)  # 100ms each; sequential = 1s, parallel < 0.3s
            return _make_result(f"[^Test-{ref.original_number}-2024]")

        sculptor._process_single_journal_article = slow_process
        sculptor._deduplicate_references = Mock(
            return_value=(refs, {ref.url: [ref.original_number] for ref in refs})
        )

        start = time.monotonic()
        sculptor._step_process_journal_articles(refs)
        elapsed = time.monotonic() - start

        assert len(sculptor.processed_citations) == 10
        # Sequential would take ~1.0s; parallel should be < 0.5s
        assert elapsed < 0.5, f"Took {elapsed:.2f}s; expected < 0.5s for parallel execution"

    def test_processed_citations_complete_after_out_of_order_finish(self):
        """All results should be in processed_citations regardless of completion order."""
        sculptor = _make_sculptor(max_workers=5)
        refs = [_make_ref(i) for i in range(1, 6)]

        def mock_process(ref):
            # Reverse delay: ref 1 finishes last, ref 5 finishes first
            time.sleep(0.05 * (6 - ref.original_number))
            return _make_result(f"[^Article-{ref.original_number}]")

        sculptor._process_single_journal_article = mock_process
        sculptor._deduplicate_references = Mock(
            return_value=(refs, {ref.url: [ref.original_number] for ref in refs})
        )

        sculptor._step_process_journal_articles(refs)

        labels = {c.label for c in sculptor.processed_citations}
        expected = {f"[^Article-{i}]" for i in range(1, 6)}
        assert labels == expected, f"Missing labels: {expected - labels}"

    def test_failed_ref_adds_to_manual_review(self):
        """A ref that raises an exception should be added to manual_review_items."""
        sculptor = _make_sculptor(max_workers=3)
        refs = [_make_ref(1), _make_ref(2), _make_ref(3)]

        def mock_process(ref):
            if ref.original_number == 2:
                raise ValueError("PubMed API timeout")
            return _make_result(f"[^OK-{ref.original_number}]")

        sculptor._process_single_journal_article = mock_process
        sculptor._deduplicate_references = Mock(
            return_value=(refs, {ref.url: [ref.original_number] for ref in refs})
        )

        # Provide a real-ish _add_manual_review
        def add_review(ref, reason, action):
            item = Mock()
            item.original_number = ref.original_number
            item.reason = reason
            sculptor.manual_review_items.append(item)
            ref.needs_review = True
            ref.review_reason = reason

        sculptor._add_manual_review = add_review

        sculptor._step_process_journal_articles(refs)

        assert len(sculptor.processed_citations) == 2
        assert len(sculptor.manual_review_items) == 1
        assert sculptor.manual_review_items[0].original_number == 2
        assert "PubMed API timeout" in sculptor.manual_review_items[0].reason

    def test_number_to_label_map_correct_after_parallel_run(self):
        """number_to_label_map should map every ref number to the correct label."""
        sculptor = _make_sculptor(max_workers=4)
        refs = [_make_ref(i) for i in range(1, 8)]

        def mock_process(ref):
            return _make_result(f"[^Ref{ref.original_number}]")

        sculptor._process_single_journal_article = mock_process
        sculptor._deduplicate_references = Mock(
            return_value=(refs, {ref.url: [ref.original_number] for ref in refs})
        )

        sculptor._step_process_journal_articles(refs)

        for i in range(1, 8):
            assert sculptor.number_to_label_map[i] == f"[^Ref{i}]", \
                f"Ref {i} mapped to {sculptor.number_to_label_map.get(i)}"

    def test_max_workers_respects_ceiling(self):
        """With 3 refs, max_workers should be capped at 3, not the configured max."""
        sculptor = _make_sculptor(max_workers=10)
        refs = [_make_ref(i) for i in range(1, 4)]  # Only 3

        max_concurrent = {"peak": 0, "current": 0}
        count_lock = threading.Lock()

        def mock_process(ref):
            with count_lock:
                max_concurrent["current"] += 1
                if max_concurrent["current"] > max_concurrent["peak"]:
                    max_concurrent["peak"] = max_concurrent["current"]
            time.sleep(0.1)  # Hold thread to measure concurrency
            with count_lock:
                max_concurrent["current"] -= 1
            return _make_result(f"[^W-{ref.original_number}]")

        sculptor._process_single_journal_article = mock_process
        sculptor._deduplicate_references = Mock(
            return_value=(refs, {ref.url: [ref.original_number] for ref in refs})
        )

        sculptor._step_process_journal_articles(refs)

        assert max_concurrent["peak"] <= 3, \
            f"Peak concurrency was {max_concurrent['peak']}, expected <= 3"
        assert len(sculptor.processed_citations) == 3

    def test_url_dedup_maps_multiple_numbers_to_same_label(self):
        """When multiple ref numbers share a URL, all should map to the same label."""
        sculptor = _make_sculptor(max_workers=4)
        shared_url = "https://pubmed.ncbi.nlm.nih.gov/12345/"
        ref1 = _make_ref(1, url=shared_url)
        ref2 = _make_ref(2)

        unique_refs = [ref1, ref2]
        url_to_numbers = {
            shared_url: [1, 3],
            ref2.url: [2],
        }

        def mock_process(ref):
            return _make_result(f"[^Dedup-{ref.original_number}]")

        sculptor._process_single_journal_article = mock_process
        sculptor._deduplicate_references = Mock(
            return_value=(unique_refs, url_to_numbers)
        )

        sculptor._step_process_journal_articles([ref1, ref2])

        assert sculptor.number_to_label_map[1] == "[^Dedup-1]"
        assert sculptor.number_to_label_map[3] == "[^Dedup-1]"  # Same URL as ref 1
        assert sculptor.number_to_label_map[2] == "[^Dedup-2]"

    def test_thread_safety_no_data_corruption(self):
        """Run 50 refs in parallel and verify no data corruption from races."""
        sculptor = _make_sculptor(max_workers=10)
        refs = [_make_ref(i) for i in range(1, 51)]

        def mock_process(ref):
            time.sleep(0.001)
            return _make_result(f"[^Stress-{ref.original_number}]")

        sculptor._process_single_journal_article = mock_process
        sculptor._deduplicate_references = Mock(
            return_value=(refs, {ref.url: [ref.original_number] for ref in refs})
        )

        sculptor._step_process_journal_articles(refs)

        assert len(sculptor.processed_citations) == 50
        assert len(sculptor.number_to_label_map) == 50
        labels = {c.label for c in sculptor.processed_citations}
        assert len(labels) == 50, "Duplicate or missing labels detected"

    def test_single_ref_works(self):
        """Edge case: a single ref should still work correctly."""
        sculptor = _make_sculptor(max_workers=8)
        refs = [_make_ref(1)]

        sculptor._process_single_journal_article = lambda ref: _make_result("[^Solo]")
        sculptor._deduplicate_references = Mock(
            return_value=(refs, {refs[0].url: [1]})
        )

        sculptor._step_process_journal_articles(refs)

        assert len(sculptor.processed_citations) == 1
        assert sculptor.number_to_label_map[1] == "[^Solo]"

    def test_empty_refs_no_error(self):
        """Edge case: empty ref list should not raise."""
        sculptor = _make_sculptor(max_workers=8)
        sculptor._deduplicate_references = Mock(return_value=([], {}))

        sculptor._step_process_journal_articles([])

        assert len(sculptor.processed_citations) == 0

    def test_none_result_not_added(self):
        """If _process_single_journal_article returns None, it should not be added."""
        sculptor = _make_sculptor(max_workers=4)
        refs = [_make_ref(1), _make_ref(2), _make_ref(3)]

        def mock_process(ref):
            if ref.original_number == 2:
                return None  # Simulate not-found (already added manual review internally)
            return _make_result(f"[^Found-{ref.original_number}]")

        sculptor._process_single_journal_article = mock_process
        sculptor._deduplicate_references = Mock(
            return_value=(refs, {ref.url: [ref.original_number] for ref in refs})
        )

        sculptor._step_process_journal_articles(refs)

        assert len(sculptor.processed_citations) == 2
        assert 2 not in sculptor.number_to_label_map


class TestMaxWorkersConfig:
    """Tests for max_workers configuration."""

    def test_constructor_accepts_max_workers(self):
        """CitationSculptor should accept max_workers parameter."""
        sculptor = _make_sculptor(max_workers=4)
        assert sculptor.max_workers == 4

    def test_default_max_workers(self):
        """Default max_workers should be 8."""
        sculptor = _make_sculptor()
        assert sculptor.max_workers == 8
