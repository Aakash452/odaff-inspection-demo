"""Save the sample inspection through the real pipeline and write its PDF.

    python scripts/generate_sample.py  ->  sample_output/CF-2026-000001.pdf
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402
import pdf  # noqa: E402
from forms import feed_inspection as F  # noqa: E402
from scripts.sample_payload import sample_payload  # noqa: E402
from validation import validate  # noqa: E402

db.init_db()
payload = sample_payload()
clean, errors = validate(payload)
if errors:
    sys.exit(f"Sample failed validation: {errors}")
inspection_id, number = db.save_inspection(clean, F.FORM_CODE, F.NUMBER_PREFIX, payload)
name, content, digest = pdf.build_pdf(inspection_id)
out = Path(__file__).resolve().parents[1] / "sample_output"
out.mkdir(exist_ok=True)
(out / name).write_bytes(content)
print(f"Saved inspection {number} (id {inspection_id}); PDF {out / name} sha256={digest[:16]}...")
