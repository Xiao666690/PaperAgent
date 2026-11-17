import unittest
from core.common.types import EvidenceChunk
from core.evidence.formatter import format_evidence, build_citations

class DisplayNameEvidenceTests(unittest.TestCase):
    def test_renamed_file_shown_in_prompt_internal_ids_retained_for_links(self):
        internal_id = "26f629aa39087db0050d71a1c6f8d8ce"
        chunk = EvidenceChunk(chunk_id=internal_id + ":chunk", document_id=internal_id,
            knowledge_id="library", source="res/pdf/" + internal_id + ".pdf",
            page_number=3, text="MTAD-GAT uses graph attention.")
        text, mapping = format_evidence([chunk], {internal_id: "图注意力异常检测.pdf"})
        self.assertIn("论文库文件名=图注意力异常检测.pdf", text)
        self.assertIn("页码=3", text)
        self.assertNotIn(internal_id, text)
        citation = build_citations(mapping)[0]
        self.assertEqual(citation.document_id, internal_id)
        self.assertEqual(citation.knowledge_id, "library")
        self.assertEqual(citation.page_number, 3)

    def test_multiple_files_have_independent_names(self):
        chunks = [EvidenceChunk(chunk_id=f"chunk-{i}", document_id=f"id-{i}",
            source="", page_number=1, text=f"Abstract {i}") for i in range(2)]
        text, _ = format_evidence(chunks, {"id-0": "P09.pdf", "id-1": "新的自定义名称.pdf"})
        self.assertIn("[C1] 论文库文件名=P09.pdf", text)
        self.assertIn("[C2] 论文库文件名=新的自定义名称.pdf", text)
