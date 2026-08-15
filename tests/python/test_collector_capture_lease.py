import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]


def source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8-sig")


def autoit_function(text: str, name: str) -> str:
    start = text.index(f"Func {name}(")
    return text[start : text.index("EndFunc", start)]


class CollectorCaptureLeaseTests(unittest.TestCase):
    def test_full_resource_search_preserves_capture_default_but_allows_a_frame_lease(self):
        body = autoit_function(source("COCBot/functions/Pixels/_MultiPixelSearch.au3"), "_FullResPixelSearch")
        self.assertIn("$bNeedCapture = $g_bCapturePixel", body)
        self.assertEqual(body.count("_GetPixelColor"), 2)
        self.assertEqual(body.count("_GetPixelColor($x, $iY, $bNeedCapture)"), 1)
        self.assertEqual(body.count("_GetPixelColor($x + $xSkip, $iY, $bNeedCapture)"), 1)
        self.assertNotIn("_GetPixelColor($x, $iY, $g_bCapturePixel)", body)

    def test_collector_decision_and_post_input_proof_each_share_one_frame(self):
        body = autoit_function(source("COCBot/functions/Village/Collect.au3"), "Collect")
        self.assertEqual(body.count("ForceCaptureRegion()"), 2)
        self.assertEqual(body.count("_CaptureRegions()"), 2)
        self.assertEqual(body.count("$g_bNoCapturePixel)"), 6)
        self.assertIn("CollectorBubbleRecognize($g_hHBitmap2)", body)
        self.assertNotIn("returnMultipleMatchesOwnVillage", body)

        first_capture = body.index("ForceCaptureRegion()")
        first_full = body.index("Local $aGoldFull = _FullResPixelSearch")
        template_read = body.index("CollectorBubbleRecognize")
        click = body.index("Click($iCollectX, $iCollectY")
        second_capture = body.index("ForceCaptureRegion()", first_capture + 1)
        final_full = body.index("\t$aGoldFull = _FullResPixelSearch", second_capture)
        self.assertLess(first_capture, first_full)
        self.assertLess(first_full, template_read)
        self.assertLess(template_read, click)
        self.assertLess(click, second_capture)
        self.assertLess(second_capture, final_full)


if __name__ == "__main__":
    unittest.main()
