import os
import pytest

import qlib_ext_se


@pytest.mark.skipif(
    not os.environ.get("SE_PROVIDER_URI"),
    reason="Requires SE_PROVIDER_URI to point to Swedish qlib data",
)
def test_dataset_smoke():
    import qlib
    from qlib.data.dataset import DatasetH
    from qlib.data.dataset.handler import DataHandlerLP

    qlib_ext_se.register()

    qlib.init(
        provider_uri=os.environ["SE_PROVIDER_URI"], region="se", logging_config=None
    )

    # Tiny handler config; assumes provider has required fields
    handler = DataHandlerLP(
        instruments=["OMXS30"],
        start_time="2025-06-18",
        end_time="2025-06-26",
        freq="day",
        infer_processors=[],
        learn_processors=[],
    )

    ds = DatasetH(handler, segments={"train": ("2025-06-18", "2025-06-26")})
    data = ds.prepare("train")
    assert data[0] is not None
