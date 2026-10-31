"""Fail CI except exact reviewed public pins and immutable verification snapshots."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PROFILE = "src/siro/services/agent/gpt_oss_profile.json"
# Public blob and detector fingerprints: FIX-016/scan-public-fingerprint-binding.json.
PROFILE_SHA256 = (
    "3fbccde17033b8443aee5a26e1824c88955b8418c955b03ef003c712939a645e"  # pragma: allowlist secret
)
PUBLIC_PINS = {
    (3, "1d403576bfa0919fac728d081b7d3730ab5274e1"),  # pragma: allowlist secret
    (7, "000cca28ecda60515feca539cdf16adac987fa1a"),  # pragma: allowlist secret
    (8, "a074e33a8b7597cf69d7a35d59a8e238cef430cf"),  # pragma: allowlist secret
    (9, "8ebd7373145de425bee23fbd71343dd1db3e7627"),  # pragma: allowlist secret
    (10, "3657a04a520af8371b7f923474b3b91e1040d516"),  # pragma: allowlist secret
    (11, "9833b8adf7737438ef1bc5a313ca0f97e3b1992f"),  # pragma: allowlist secret
}


# FIX-026: immutable audited bytes AND their complete scanner findings batch.
# See docs/evidence/FIX-026-2026-10-16/semantic-audit.json.
REVIEWED_SNAPSHOTS = {
    "docs/runtime-evolution/SOURCE_INVENTORY.json": (
        104,
        (
            "defc0c12c09e7695cfad67f7cf8e25de"  # pragma: allowlist secret
            "2f860f496856a857a6a553033723e6ef"  # pragma: allowlist secret
        ),
        (
            "470b5429bbd2b89ef7de0669c13ff9a3"  # pragma: allowlist secret
            "9e97488c34aa9022dcd4fb09b49f3d32"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT005_reverification_2026-10-01/source-snapshot.json": (
        120,
        (
            "eba8b23d59ffd494a798d316044dc760"  # pragma: allowlist secret
            "4ea5cb5cc293920ffd1622096a219730"  # pragma: allowlist secret
        ),
        (
            "6ffe496087286a8c527f2b7c8d57cc7c"  # pragma: allowlist secret
            "78dbbfbf2906be1a079725a9671733ac"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT006_2026-10-01/gpu.log": (
        2,
        (
            "803a62637ad3fcaa34e510a48faf8cde"  # pragma: allowlist secret
            "5d00c130fd20224dccceadc4f1da008c"  # pragma: allowlist secret
        ),
        (
            "6fe57011542290ed649726f2203d6c6c"  # pragma: allowlist secret
            "229bd71083c1dc8da1af3bc6961c4a0b"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT006_2026-10-01/source-snapshot.json": (
        136,
        (
            "504303671219d35045464a3bc57fb055"  # pragma: allowlist secret
            "c4d8148815a843610ace16aabbefa96d"  # pragma: allowlist secret
        ),
        (
            "7e434a8c348821c0706d6e0fbafbb924"  # pragma: allowlist secret
            "a40e3347f862b6aaf464dd0612f504d2"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT007_2026-10-02/source-snapshot.json": (
        120,
        (
            "a4de80378dd9abc8822173740c21895d"  # pragma: allowlist secret
            "2ae45e5ac51f30e30330206c19bccf1d"  # pragma: allowlist secret
        ),
        (
            "f7977e39a3a62caf7118e9bcdc5ba8a9"  # pragma: allowlist secret
            "aff6f76513c391f5f4350f348d4dd994"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT009_reverification_2026-10-05/source-snapshot.json": (
        121,
        (
            "4dea35e35e17ef7521bcb5c59ba6584c"  # pragma: allowlist secret
            "340260cf7df4e0c0ae0cc2698aa9931b"  # pragma: allowlist secret
        ),
        (
            "4ecee6b635a010e20da8d9bba9a2ccda"  # pragma: allowlist secret
            "501161459b4c18de0b08c5632237d023"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT010_2026-10-05/source-snapshot.json": (
        121,
        (
            "66528a685475fedce0364a320b9eafb9"  # pragma: allowlist secret
            "0da14b917b2ffa69322ca5080af458c0"  # pragma: allowlist secret
        ),
        (
            "4c8034cd620e9081ca4b204edef5ac56"  # pragma: allowlist secret
            "fe3f8dde4ff66b101223fe0f948070dd"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT011_2026-10-05/source-snapshot.json": (
        124,
        (
            "bf8c12210d7d067fe299dd117aa40a0b"  # pragma: allowlist secret
            "3d8f5ddcfbed020e7133bd9913a8c361"  # pragma: allowlist secret
        ),
        (
            "8ddfda579863adc3f803b4e3a2d25d04"  # pragma: allowlist secret
            "2acc664d44180de7d4483a6aa88b168e"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT011_2026-10-05/test_independent.py": (
        1,
        (
            "2649955abeddc20e070b57f66f224095"  # pragma: allowlist secret
            "725d06ebd4777a477a4d0c6cd1ca0638"  # pragma: allowlist secret
        ),
        (
            "c8b785831a67f748b2e4dfe794ee64e6"  # pragma: allowlist secret
            "b0f3e5d26c1468bac50de0e59e7fecd5"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT012_2026-10-05/source-snapshot.json": (
        125,
        (
            "de6f376d19a96b54cb570370dbe00082"  # pragma: allowlist secret
            "d6fb3ef753be9b8f163bab036ed23277"  # pragma: allowlist secret
        ),
        (
            "e8de167422788479b5071b35a546c083"  # pragma: allowlist secret
            "cb8cfafdc36ced2424bbea39e7624616"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT014_2026-10-05/source-snapshot.json": (
        125,
        (
            "4fdebac0ae3295e5fa212d8fff88fc34"  # pragma: allowlist secret
            "e7dcce1804af847871a4446bf2f07ee7"  # pragma: allowlist secret
        ),
        (
            "c146cca21276e16ed0dca8ab66e04867"  # pragma: allowlist secret
            "aba24f523fe37219f95b4b9d45edc6d8"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/architecture_review_2026-10-03/source-digests.json": (
        110,
        (
            "22232a316ab8f7b7f110b0a148f70781"  # pragma: allowlist secret
            "da08a197c1b7819548e6f55fbdad0cdc"  # pragma: allowlist secret
        ),
        (
            "928ecf5995a14e323edcd7450f2c6cd4"  # pragma: allowlist secret
            "992dcd7def511d632544ad1425ae29a4"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/architecture_review_2026-10-05/source-digests.json": (
        123,
        (
            "74ab1f34f07b561d3ec0c57889061994"  # pragma: allowlist secret
            "50f06843a4a90b6d7d91794db59abb4b"  # pragma: allowlist secret
        ),
        (
            "fafa3cbe276ca8c481fa5dbb2f437eca"  # pragma: allowlist secret
            "edfae74bc08ee262dc6c338fc26515c4"  # pragma: allowlist secret
        ),
    ),
    # Public content digests and reviewed verification artifacts.
    # Each entry is bound to the exact file bytes and the full detector batch.
    "assets/companion/haru-upperbody/0.1.0/pack.json": (
        11,
        (
            "d9b65f71da57f3699996049a6df51386"  # pragma: allowlist secret
            "1bae884d0c9ddb82da62c2e5f8858137"  # pragma: allowlist secret
        ),
        (
            "aed0f7dcc863a7889bff89c8004c253a"  # pragma: allowlist secret
            "88c12becf46cef0202199b0461d05456"  # pragma: allowlist secret
        ),
    ),
    "assets/companion/siro-original/3d-style-study/0.1.0/manifest.json": (
        7,
        (
            "1664ccdccde948cd870635ed8ea27df3"  # pragma: allowlist secret
            "8a71bdc7e7412fa8d5ba57d8a9a47010"  # pragma: allowlist secret
        ),
        (
            "c10a369a76a323ea59e851665d7c5e1d"  # pragma: allowlist secret
            "21429cc3bbb5e7a130ad347f25fd746f"  # pragma: allowlist secret
        ),
    ),
    "assets/companion/siro-original/material-study/0.1.0/material-manifest.json": (
        7,
        (
            "1f1d6486b397f9172587bf0300ec5e47"  # pragma: allowlist secret
            "286835cfd6f0446c87e62d999f30175c"  # pragma: allowlist secret
        ),
        (
            "bf4205ff2d63e8bb3b3cd1f6f8dbce91"  # pragma: allowlist secret
            "0bcd7bc49c4de018f8ecaf749e9031e0"  # pragma: allowlist secret
        ),
    ),
    "assets/companion/siro-original/material-study/0.2.0/material-manifest.json": (
        10,
        (
            "b232bc16c0a15675b881d76671705130"  # pragma: allowlist secret
            "a097c4c1b2bb6986c7b280d0ddaa0937"  # pragma: allowlist secret
        ),
        (
            "1a5d6d4cb8de1f54ca57cf863b91cd98"  # pragma: allowlist secret
            "04b71736744cc3656285fee765d4aa07"  # pragma: allowlist secret
        ),
    ),
    "assets/companion/siro-original/material-study/0.3.0/material-manifest.json": (
        14,
        (
            "9495a2bdf53c649fbbb4e54ca2a10b39"  # pragma: allowlist secret
            "3c4a57a843612a2a7eb4c1b706a6ee15"  # pragma: allowlist secret
        ),
        (
            "7cb5e3af5d95714171e9f6d52164881b"  # pragma: allowlist secret
            "a9b7723d4e8e1ff9560d0fb958d8288f"  # pragma: allowlist secret
        ),
    ),
    "assets/companion/siro-original/toolchain-roundtrip/0.1.0/manifest.json": (
        8,
        (
            "f4e7bb4c8c6dc9e2ed77696eb36712f1"  # pragma: allowlist secret
            "fca0aef43bddb14fae96cc2ca8bfc6ca"  # pragma: allowlist secret
        ),
        (
            "c9d55349d8a13995ae644b7b0529175a"  # pragma: allowlist secret
            "034cfa4b8368c0365fb6e0acfe2ccefa"  # pragma: allowlist secret
        ),
    ),
    "assets/companion/siro-original/toolchain-roundtrip/0.2.0/manifest.json": (
        7,
        (
            "ddb4c6e001baec51e2a0719214db1053"  # pragma: allowlist secret
            "0b37499a21ca2130c05b388eaf59a358"  # pragma: allowlist secret
        ),
        (
            "9b843badf5e26853a2700096ce54285d"  # pragma: allowlist secret
            "1f6198557b49712a8fe07647721793b5"  # pragma: allowlist secret
        ),
    ),
    "assets/companion/siro-vrm/0.1.0/pack.json": (
        37,
        (
            "c579ec049ba9f2e00eee28586fe4cbd4"  # pragma: allowlist secret
            "33790a9cf20e6f2fdfd6e55d2c1478d0"  # pragma: allowlist secret
        ),
        (
            "556cebd4bb915c8433bcdd1f45ec4f99"  # pragma: allowlist secret
            "2fb6856402cb971982f9b14193c8db54"  # pragma: allowlist secret
        ),
    ),
    "design/companion/CP-V01/asset-inventory.json": (
        48,
        (
            "a21560a07d0d76d4a9276e34aeac6ea4"  # pragma: allowlist secret
            "a265f4fc4f7e3cf13ea56a7239b02731"  # pragma: allowlist secret
        ),
        (
            "b4121136ccc7c0dad64f6a321718c00f"  # pragma: allowlist secret
            "1f6b92c3633180b52c71d263bfaca3aa"  # pragma: allowlist secret
        ),
    ),
    "design/companion/CP-V01/preview-artifacts.json": (
        47,
        (
            "b2d5cecaf237f54bf355d22327ef9ff8"  # pragma: allowlist secret
            "5802993cbff441e85e3e2bc4421870df"  # pragma: allowlist secret
        ),
        (
            "4d7de686d92f0c6d0a33665732a55d08"  # pragma: allowlist secret
            "fe3ed7928d53f5b74af190543ba75c5e"  # pragma: allowlist secret
        ),
    ),
    "design/companion/CP-V02/pack-digests.json": (
        9,
        (
            "93fbad094db76208ad8a082012705681"  # pragma: allowlist secret
            "d52e6e09ad1933bd239dcc74739b6d1d"  # pragma: allowlist secret
        ),
        (
            "d46942545222796772ab0df1f8c09e39"  # pragma: allowlist secret
            "2110a24be29c027454d0521dbf67d399"  # pragma: allowlist secret
        ),
    ),
    "design/companion/CP-V02/preview-artifacts.json": (
        34,
        (
            "ee3d1c85001eb0db9de80c358907f1ef"  # pragma: allowlist secret
            "5a43e215e126910fd956d5a3f41f98e5"  # pragma: allowlist secret
        ),
        (
            "dee72593245e8e349875fb9b21157352"  # pragma: allowlist secret
            "1037ed32568687176740755ea2565232"  # pragma: allowlist secret
        ),
    ),
    "design/companion/CP-V03/concept-artifact-0.1.0.json": (
        1,
        (
            "f69b9992648ec21fe946453478ccdfc5"  # pragma: allowlist secret
            "580b91d72a831800cfa4d3b9f89bacd1"  # pragma: allowlist secret
        ),
        (
            "434bec7e0645b162a55fe44b87cc4ca4"  # pragma: allowlist secret
            "574bc2696c32c27b03abecdfef578403"  # pragma: allowlist secret
        ),
    ),
    "design/companion/CP-V03/concept-artifact.json": (
        2,
        (
            "c17c2dfc7bdc36c6ee1d6ee719f18e0e"  # pragma: allowlist secret
            "c74a01e1c9aed57ddbbaee6ade9b9b63"  # pragma: allowlist secret
        ),
        (
            "e6d951e90852f108fc15aa72000f3a5c"  # pragma: allowlist secret
            "debda7877e28e2622186c08e1083536a"  # pragma: allowlist secret
        ),
    ),
    "design/companion/CP-V03/mcp-connection-2026-10-19/receipt.json": (
        2,
        (
            "38a9315aca61fedc1f43ff7f58182bf5"  # pragma: allowlist secret
            "3ae5880cca9bf019c189b7ca4151fe85"  # pragma: allowlist secret
        ),
        (
            "a87c221a7c896259fbc628d3ce36ee40"  # pragma: allowlist secret
            "be3ee0ae835db19198da3fd655890821"  # pragma: allowlist secret
        ),
    ),
    "design/companion/CP-V03/mcp-connection-2026-10-19/stdio-probe.json": (
        1,
        (
            "71a1a6e4a144ea24b22efb6992d9c044"  # pragma: allowlist secret
            "4268be6f31379b9d85d2d7029ced04c2"  # pragma: allowlist secret
        ),
        (
            "24fcb0b0f274c9423b82bd320cdcb9ad"  # pragma: allowlist secret
            "2c2dd46f352a37ec98e3d36561fd10d0"  # pragma: allowlist secret
        ),
    ),
    "design/companion/CP-V03/roundtrip-fixture/0.1.0/file-validation.json": (
        4,
        (
            "e1e4d65de0b5d2f0615625a09d70fc6c"  # pragma: allowlist secret
            "e0fc098d69ebe4ea7bfeb6cdd1ac98b8"  # pragma: allowlist secret
        ),
        (
            "8588a014cacede4b2791e72514f762ce"  # pragma: allowlist secret
            "348933bc3408c4656cd6c6c6b8796bb0"  # pragma: allowlist secret
        ),
    ),
    "design/companion/CP-V03/roundtrip-verification-2026-10-19/archived-comparison.json": (
        6,
        (
            "c03fd7d7451fcb28e86c822b2085b7d8"  # pragma: allowlist secret
            "d7ffde84fde65960456e2ed20514d3a2"  # pragma: allowlist secret
        ),
        (
            "863b05553a4b93e501c7e48f5a070e43"  # pragma: allowlist secret
            "e0448a5677d71bef2f3c54a0e8e87278"  # pragma: allowlist secret
        ),
    ),
    "design/companion/CP-V03/roundtrip-verification-2026-10-19/comparison.json": (
        6,
        (
            "ca7d533971597055f9f8a989ab323702"  # pragma: allowlist secret
            "d2afa40d0d8767cbbfaf2982f52a269c"  # pragma: allowlist secret
        ),
        (
            "869e4016ef1e26fa51c591f62f503a4b"  # pragma: allowlist secret
            "ad0962ef6c2284edc386e71b7e76f588"  # pragma: allowlist secret
        ),
    ),
    "design/companion/CP-V03/roundtrip-verification-2026-10-19/v1-final/report.json": (
        5,
        (
            "03ed4ca957f38a9c47ff113100fb705c"  # pragma: allowlist secret
            "aaad451cb8fddc86e38a2f4fc5ea3035"  # pragma: allowlist secret
        ),
        (
            "4c8084e22ed15a3a352a43542faa2889"  # pragma: allowlist secret
            "6aee34cebab92a492027413b35be949d"  # pragma: allowlist secret
        ),
    ),
    "design/companion/CP-V03/roundtrip-verification-2026-10-19/v2-final/report.json": (
        5,
        (
            "a696a07ec71be472545c7004319eb1a3"  # pragma: allowlist secret
            "1f4936ed2125e54d5e5d64bdc343daf7"  # pragma: allowlist secret
        ),
        (
            "e20bbf34391e01298a2e5b789a84caf6"  # pragma: allowlist secret
            "d7c670a3e1fd1ce171e24fed4f1a9974"  # pragma: allowlist secret
        ),
    ),
    "design/companion/CP-V03/wine-2026-10-19/receipt.json": (
        1,
        (
            "190b26b489dccb8d70ba7c783449cecf"  # pragma: allowlist secret
            "20b9fb663b9a93839aea4d9f528ab46c"  # pragma: allowlist secret
        ),
        (
            "6254cefea12531e1b667641ea5f10ba7"  # pragma: allowlist secret
            "4b2c309822b74c2760a4d6af1dd7c345"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM-GATE-IMPORT/final-receipt.json": (
        3,
        (
            "b785ce3b99dcba98b2fc4e67871f09e1"  # pragma: allowlist secret
            "0ee127debf63dfdaf0d969e28ec9d228"  # pragma: allowlist secret
        ),
        (
            "5a5596ce241148edebc5cee21a024e03"  # pragma: allowlist secret
            "345fc5dbcb8fd73f36c26e83c234ff4e"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM-RUNTIME-INTEGRATION/REPORT.md": (
        2,
        (
            "0779a930b5adcf8714b3efe68c4214b8"  # pragma: allowlist secret
            "a176fda4025ee9239a6a2d80a5197281"  # pragma: allowlist secret
        ),
        (
            "51ffdaf1fea1b0d7b6fe184d69d22667"  # pragma: allowlist secret
            "a1e4a457dc2a9a3206d01a8663651010"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM-RUNTIME-INTEGRATION/full-v1-receipt.json": (
        3,
        (
            "2d7b9c80338a723c58061dd3455484a9"  # pragma: allowlist secret
            "b27d79f1ff715d7bc76d2c0407bbae96"  # pragma: allowlist secret
        ),
        (
            "5a8fcb17714a6e9b0ac40b33e86e3806"  # pragma: allowlist secret
            "03d724882284e89388bb4dcbfaa990ef"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM-RUNTIME-INTEGRATION/selected-v2-receipt.json": (
        3,
        (
            "6a7867ff2d74b23c6c8f28769d4422f9"  # pragma: allowlist secret
            "ee967dbcba9a34d4ea375f35c1ff136f"  # pragma: allowlist secret
        ),
        (
            "3feb26c2122bbc331d341fcb5958ed2b"  # pragma: allowlist secret
            "d7406878888389e4fd6cca3d80312b3f"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM-RUNTIME-INTEGRATION/selected-v3-receipt.json": (
        3,
        (
            "d8c733739ee524dbcc32e8c9094a7746"  # pragma: allowlist secret
            "0a4500ec4cfb769d3c9ffc6a61e39e65"  # pragma: allowlist secret
        ),
        (
            "f225ad1593c9ea8b761f2a7da5260886"  # pragma: allowlist secret
            "37c0bf7f037ed415c46743fe93c4eac5"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-BODY-REVIEW/capture.json": (
        8,
        (
            "5c94edf7f0cf48d6bee371beed35ed62"  # pragma: allowlist secret
            "9c5df131e0c6bd567db0ab8b7a707575"  # pragma: allowlist secret
        ),
        (
            "a9aed270f1a270a1d127125d7f553367"  # pragma: allowlist secret
            "2896fcb4e31f235da0a6436793e0b4a4"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-BODY-REVIEW/final-receipt.json": (
        3,
        (
            "5f1e36fe46a93289b78a332e717eca9f"  # pragma: allowlist secret
            "2e2b6b58be6fad8ad1fbc408fbf06f04"  # pragma: allowlist secret
        ),
        (
            "93aa171db43b3e18c503094ead85c840"  # pragma: allowlist secret
            "ab185389671794ce085c90b72487305c"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-BODY-REVIEW/historical-inputs.base64.json": (
        3,
        (
            "3f286aaa9ddcabfef973d63038abb7b1"  # pragma: allowlist secret
            "b35e9221f4b331361bbdc6f418d6ee9f"  # pragma: allowlist secret
        ),
        (
            "cd843c6d03f69dfd5a8eb09a83853a09"  # pragma: allowlist secret
            "3b8f7eb8451de4acf4117fe470d7c7ec"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-BODY-REVIEW/projection-body-review.json": (
        31,
        (
            "a9fdc1036972ac165749761a654adf42"  # pragma: allowlist secret
            "a21f286c959427367b675ce9bb27fb74"  # pragma: allowlist secret
        ),
        (
            "91bbc7cdb263191b5b21967f0552ea5e"  # pragma: allowlist secret
            "a265431b0197e7cff89f8cfd2fa0ce2a"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-BODY-REVIEW/reviewed-result.json": (
        34,
        (
            "1c172b7110728acbf43227d7fe75b593"  # pragma: allowlist secret
            "6e84a4df66b6eb289e8f9fc67f06e93a"  # pragma: allowlist secret
        ),
        (
            "3e34ba19d96f64eda7aa5a24ba7487fd"  # pragma: allowlist secret
            "f4c119639374f158b264e4fb424f1a16"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-CONTEXT-QUALITY/baseline-real.json": (
        8,
        (
            "7df5f8d1f7c7a5776ab4fa97c5e98426"  # pragma: allowlist secret
            "a8ee06d1929d8b0152fe7558ea6d9f4b"  # pragma: allowlist secret
        ),
        (
            "22a5c52c63021baa0151e1e22b242130"  # pragma: allowlist secret
            "99191eac5fcdca4f46d853dad96c2597"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-CONTEXT-QUALITY/baseline-review.json": (
        30,
        (
            "2219f76e51928e356b8b7ab446000078"  # pragma: allowlist secret
            "fc4298876e6f0c2f346d247ca45d873a"  # pragma: allowlist secret
        ),
        (
            "e5f18092bc2b041638bb36a81a810bed"  # pragma: allowlist secret
            "d8652b21c2c6e769c1ca31a8dd08535f"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-CONTEXT-QUALITY/baseline-reviewed.json": (
        32,
        (
            "d1cf141d3d8ab72083ae79cdb854ab3f"  # pragma: allowlist secret
            "069758e5e3fcce31c8b88236bc076115"  # pragma: allowlist secret
        ),
        (
            "3b19e47f648496ebbe61bb8224b5e985"  # pragma: allowlist secret
            "3b8dc54fe9846de11a91c0d75d51159e"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-CONTEXT-QUALITY/candidate-real.json": (
        8,
        (
            "3688955c845b9372f34251462f26842e"  # pragma: allowlist secret
            "d29a60ca278745a24825bd3cf5610fca"  # pragma: allowlist secret
        ),
        (
            "c92a3da3d5e62de147d886899251f6af"  # pragma: allowlist secret
            "6e93c689d82f98ce9d45232bd07e0ca4"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-CONTEXT-QUALITY/candidate-review.json": (
        32,
        (
            "368f7b49e5eca7a79022625b2ef73316"  # pragma: allowlist secret
            "f67e5a2eb84d59cdd4d8bce98625bf00"  # pragma: allowlist secret
        ),
        (
            "c81ea88f268feaac0cab88dd53429c67"  # pragma: allowlist secret
            "5ee70f2b755b1fe2012e7d85c65e4b44"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-CONTEXT-QUALITY/candidate-reviewed.json": (
        34,
        (
            "c68639edcf2a032c15fb1d29b7167833"  # pragma: allowlist secret
            "37c2678a817e58ed7e8e750bc1b23fdd"  # pragma: allowlist secret
        ),
        (
            "4fc26ace2c038205274c68d944860c0a"  # pragma: allowlist secret
            "b44037c731b478a4940b86aa7534db38"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-CONTEXT-QUALITY/context-capacity-diagnostic.json": (
        2,
        (
            "73476d90981b0f12f80d1cd5501ebc52"  # pragma: allowlist secret
            "21dc080029b8ef18293a84b4308bfd9d"  # pragma: allowlist secret
        ),
        (
            "ef7ac667c35ed91c11d225a8ab5f7cf7"  # pragma: allowlist secret
            "bda98e10a147abcefad7a9e40b841b34"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-CONTEXT-QUALITY/final-receipt.json": (
        3,
        (
            "0ed233d0592ede3d262e38d9e3af20df"  # pragma: allowlist secret
            "9f5b543b44cbbf094c2db2bb1834af2b"  # pragma: allowlist secret
        ),
        (
            "4af8849a8ee1d5ab8599d877926571c9"  # pragma: allowlist secret
            "b0a9762c3213e19c5cebbebc16f13727"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-CONTEXT-QUALITY/model-after.json": (
        1,
        (
            "af51cf8aa8739009865a7f28a737ede9"  # pragma: allowlist secret
            "e9fc019261613d9dcc17971df100570e"  # pragma: allowlist secret
        ),
        (
            "8cc5fa3819b499a6709fd24f20ca9f03"  # pragma: allowlist secret
            "85bb4f99334bfb8c5212ed5f55821bf5"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-CONTEXT-QUALITY/review-inputs.base64.json": (
        5,
        (
            "0c102d61c91725b8e03a6843323719d2"  # pragma: allowlist secret
            "2f9f71a45b0d6a81496179168f0b0331"  # pragma: allowlist secret
        ),
        (
            "09e593c6fa92015cae617cf52924f934"  # pragma: allowlist secret
            "ec0d97c2cf1e94f4ae026b1cbb8139e8"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-MODEL-INPUT-FIX/example-contamination-check.json": (
        1,
        (
            "e1e48a6e6c62c7f82b631b0176e260fa"  # pragma: allowlist secret
            "4a35d1dc4a96c2ca6891cc08a19e2bd1"  # pragma: allowlist secret
        ),
        (
            "cd50c6793fe1ca1db7fb748ef90c538f"  # pragma: allowlist secret
            "91c2166ef28839e80e89493d2720bedc"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-MODEL-INPUT-FIX/final-receipt.json": (
        3,
        (
            "d866d119f1bde95479684f96b8bfbc28"  # pragma: allowlist secret
            "17b5b31bf1ce6c8eb4219f5bd645455d"  # pragma: allowlist secret
        ),
        (
            "041bb7ae4aea6c4f8bc8095cb6e9943c"  # pragma: allowlist secret
            "20f819b860e9cf358ab5710d69c7d1a0"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-MODEL-INPUT-FIX/holdout-v4-review.json": (
        14,
        (
            "dbbbe728bdd77d20aefebe1a2bbcf927"  # pragma: allowlist secret
            "58a59b17e5129858ed0f89d918e90df7"  # pragma: allowlist secret
        ),
        (
            "4112720e32154e0a65a6d7a6281a81f5"  # pragma: allowlist secret
            "d86dfc720f5384e53377ba0982fe7b92"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-MODEL-INPUT-FIX/holdout-v4-reviewed.json": (
        16,
        (
            "3cdba20b13a823652c8c4c2d2a135706"  # pragma: allowlist secret
            "f02fa4d809a61398061cdf76f2566369"  # pragma: allowlist secret
        ),
        (
            "6fd36d894f7b19d8e614f0b7fb34e93a"  # pragma: allowlist secret
            "0d492aa131d273c53a32b8677d02fa46"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-MODEL-INPUT-FIX/holdout-v4.json": (
        12,
        (
            "328ce393cb5c8b98c7380b884737aa36"  # pragma: allowlist secret
            "4c1be676bac2b569f2c4349c22f4c8ec"  # pragma: allowlist secret
        ),
        (
            "e02c6339bddd51d0c36f0baa7f9b6111"  # pragma: allowlist secret
            "09384287cb0c66b6a78191272c61e3b4"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-MODEL-INPUT-FIX/integration-proposal-base.json": (
        1,
        (
            "d65ede2893ed5f0e4ca44992c6595ff1"  # pragma: allowlist secret
            "fe9a0fa00d2c8a536af2f20be9c2c8f4"  # pragma: allowlist secret
        ),
        (
            "5cdf944056753c890c72d7e82ebde464"  # pragma: allowlist secret
            "5868ee8422d7754bd790fb6f8c3b23d6"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-MODEL-INPUT-FIX/model-metadata-final.json": (
        5,
        (
            "722e159258ba3429526470857caf4591"  # pragma: allowlist secret
            "f3dda372584a3b691ed82ae1d8c57b4f"  # pragma: allowlist secret
        ),
        (
            "4131f67ee137a77982cf837b5ac3b366"  # pragma: allowlist secret
            "d8c063d2d89996e631e81651aec13692"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-MODEL-INPUT-FIX/real-v1.json": (
        9,
        (
            "1c9c2bcf43c0ac3583799305cad06e56"  # pragma: allowlist secret
            "61b3dbef8f8e70f938ef69e7a9decd74"  # pragma: allowlist secret
        ),
        (
            "9bcc87d5657dfa4ecff0b14d0151776c"  # pragma: allowlist secret
            "cb7b32bb7cc9daa752abaa84549f754b"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-MODEL-INPUT-FIX/real-v2.json": (
        10,
        (
            "1a29fe930fa0f9f9a812d73102142b61"  # pragma: allowlist secret
            "49a14f8898ca224a994906223d3e95b9"  # pragma: allowlist secret
        ),
        (
            "fc9810eb69a5611af9ac903953c5c305"  # pragma: allowlist secret
            "6f33a3abea0944b4c6a91eaf4c537d05"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-MODEL-INPUT-FIX/real-v3.json": (
        10,
        (
            "8eb0420acb17c7b2f0eae0f6c676504a"  # pragma: allowlist secret
            "caca4c580a9f7e1f64795cdb9dad4995"  # pragma: allowlist secret
        ),
        (
            "75e16f795a36a93ee8fa1f5e8de3b9c2"  # pragma: allowlist secret
            "90335aba3610de366c514b0ab55756bc"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-MODEL-INPUT-FIX/real-v4.json": (
        10,
        (
            "8b9012a60fa1acc410571849fca7ca84"  # pragma: allowlist secret
            "71e50a7116a970ae3b2ae049bd8abd61"  # pragma: allowlist secret
        ),
        (
            "3d4aa64040f948504895f655b453d07c"  # pragma: allowlist secret
            "b55a5fefa2e26a0a71b135cb66735fff"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-MODEL-INPUT-FIX/review-inputs.base64.json": (
        6,
        (
            "3f6ab0f8b1f4b2363458f7e7ecfed1e9"  # pragma: allowlist secret
            "dc8b8656f3feac7e9542a37959a2cd83"  # pragma: allowlist secret
        ),
        (
            "7b5d60a210a84044d77dabc6885ccea8"  # pragma: allowlist secret
            "c85d013bc3bddff63c1fea761b1cf4c6"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-MODEL-INPUT-FIX/review-v4.json": (
        32,
        (
            "3fc0b12e9c56c1415332c0a85c7648df"  # pragma: allowlist secret
            "ee1b6b76918896ac60708890c576f64e"  # pragma: allowlist secret
        ),
        (
            "c83ffc55120f3724d6e3adc8ab3957d2"  # pragma: allowlist secret
            "8274ecdec5449b75d7122de92da28c53"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM02-MODEL-INPUT-FIX/reviewed-v4.json": (
        34,
        (
            "7be6c96b03e3f175f2ebd7f80ac76c53"  # pragma: allowlist secret
            "ff0c73a672e78ce9dd97fe03dff517f4"  # pragma: allowlist secret
        ),
        (
            "bde7a138a41e3e968161c641b0a501f7"  # pragma: allowlist secret
            "a0a08968678c7b252324001bcf93b230"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM04-hybrid-retrieval/development-diagnostic.json": (
        2,
        (
            "4da1a7eaa064ad344b97d2e7fbbf88ff"  # pragma: allowlist secret
            "a63175512f22455e2cf5ce1caafdd990"  # pragma: allowlist secret
        ),
        (
            "b606fbe9da6ef252c023f451808be59c"  # pragma: allowlist secret
            "418480c934572e0afe46306aef6b71c8"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM04-hybrid-retrieval/development-floor03.json": (
        2,
        (
            "b5fa02d6641b76f9fa9d5d809930ec65"  # pragma: allowlist secret
            "67473c34bb4015346af260f8f9818e4c"  # pragma: allowlist secret
        ),
        (
            "e4c9db7cda540658fe00298880672aeb"  # pragma: allowlist secret
            "9d00eca5cb84aa403a9c45626a7cf54a"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM04-hybrid-retrieval/embedding-install.json": (
        1,
        (
            "dd42e8fc028fe3740effefae59ef7395"  # pragma: allowlist secret
            "c9f3311fc0689d6d200cea8adfd0f557"  # pragma: allowlist secret
        ),
        (
            "ab1a5ec725b130260455f076f4165177"  # pragma: allowlist secret
            "9055a011cfa08e861042dcf750c14cc1"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM04-hybrid-retrieval/real-retrieval-case2.json": (
        2,
        (
            "ad5bef54d5532b67b0213726f14b3628"  # pragma: allowlist secret
            "85fa0e580deec0b8ceb08cf7d340774b"  # pragma: allowlist secret
        ),
        (
            "9f13d373c35b1ea911c90b54e2dbbe2e"  # pragma: allowlist secret
            "f51ef1149e57293e478707e2bf1a6aaa"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM04-hybrid-retrieval/regression-initial-fail/receipt.json": (
        3,
        (
            "fb69e751d6a7f4f04b3e58e3e48db0b9"  # pragma: allowlist secret
            "641e53ad4748490a0c14c396397c2526"  # pragma: allowlist secret
        ),
        (
            "8b22f73cc9a3d9c564b28e17ddd587b7"  # pragma: allowlist secret
            "7defb78e2120ee2a10436f5f11a4e987"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM04-hybrid-retrieval/regression-pass/receipt.json": (
        3,
        (
            "5a30f59a2417d8db3ef929438460a856"  # pragma: allowlist secret
            "473b92006ee82f57c124440bfdfae82c"  # pragma: allowlist secret
        ),
        (
            "e27e13a1221484d86a5ccb7e18833114"  # pragma: allowlist secret
            "2c200dcbd5a3970c29109842720932c8"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM04-hybrid-retrieval/scoped-secrets.json": (
        2,
        (
            "34f9fec54ab5ae21d3bacbe803a1ce79"  # pragma: allowlist secret
            "02ea9ae852f021e16457f9dcd410a9ea"  # pragma: allowlist secret
        ),
        (
            "18dde76a980e1e275fd8470f4dc70e43"  # pragma: allowlist secret
            "794d724b67152dbbd5fd949935252d1d"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM04-hybrid-retrieval/threshold-case1-preliminary.json": (
        2,
        (
            "4f9e0857ff0410129633687a7ec0ee65"  # pragma: allowlist secret
            "8e7f75274b44171b9bc2ab1038843ea7"  # pragma: allowlist secret
        ),
        (
            "2a10c0951d6bbb0a3c90edf04d268b94"  # pragma: allowlist secret
            "f8d3b29494043fad6b4e99c11ac9f63a"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM04B-relevance/regression-v1-receipt.json": (
        3,
        (
            "286235856a15e97530052a6fe594786f"  # pragma: allowlist secret
            "e49e8d2c96c6b532c1de4ebd2799ec4b"  # pragma: allowlist secret
        ),
        (
            "43a877aee7311db355061a13516f305c"  # pragma: allowlist secret
            "94b91b59744657208c2027a0eaeab109"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM04B-relevance/regression-v2-receipt.json": (
        3,
        (
            "947c6ece17726e15516c38d1ab41e872"  # pragma: allowlist secret
            "6362e685e71a6dc2681e749acb65c56d"  # pragma: allowlist secret
        ),
        (
            "35fa89ee254f920490e3d55b2c702e47"  # pragma: allowlist secret
            "92a4189f0ce151b34a0cc512b01e1529"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM04B-relevance/scoped-secrets.json": (
        2,
        (
            "248ec0e611021fedd11136b8bd5568d7"  # pragma: allowlist secret
            "95ff3381efef9940d733aa78a07a87a3"  # pragma: allowlist secret
        ),
        (
            "dcc99643ab58f420be9f94ad53ccede4"  # pragma: allowlist secret
            "f923b4ab307c2b9b3beef7cc3a9e8a31"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM04B-relevance/v1-contrast.json": (
        2,
        (
            "2476c7774ab5f23d42f8deb60ac4c7bb"  # pragma: allowlist secret
            "830a088da074e90c45a6e82484f68e29"  # pragma: allowlist secret
        ),
        (
            "2c814a32dc239dc99fb78c2f5e0d9f0c"  # pragma: allowlist secret
            "d9561a6d2ef72fa53c5e8f3be84c2a8b"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM04B-relevance/v2-evaluation.json": (
        2,
        (
            "22944d714d85b8e299dc9e50938d3a06"  # pragma: allowlist secret
            "c1c263d1ed6d8f894ae14fb2b6910b28"  # pragma: allowlist secret
        ),
        (
            "e1c21dee567f15e5c30e3901a34c2de0"  # pragma: allowlist secret
            "c976efb71a70fec54a698c74328ccf7e"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM04B-relevance/v3-evaluation.json": (
        2,
        (
            "12c6d7327afc0944382de325c740b8c3"  # pragma: allowlist secret
            "d8a21eada2e585cee8e369d96482e833"  # pragma: allowlist secret
        ),
        (
            "936a6a80c57fcf02e4cbb0980de3ab8b"  # pragma: allowlist secret
            "85fb95b5551e9f6bc1ee8fa8cfde52c7"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM04B-relevance/v4-contrast.json": (
        2,
        (
            "4646bf46536e3b868a5b2e28dd9d8f1b"  # pragma: allowlist secret
            "3f196e91340ff276e7f978fbdf4e3586"  # pragma: allowlist secret
        ),
        (
            "667ba9760f2662e16eefc45e10103d7d"  # pragma: allowlist secret
            "5130c80150f1735b2701f0c156560064"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM04B-relevance/v5-evaluation.json": (
        2,
        (
            "4677313557a17fd4abdf67b3d373aebc"  # pragma: allowlist secret
            "d19a200a8d0f8813bfe11d31f8fe81e7"  # pragma: allowlist secret
        ),
        (
            "34e46a1b9185c367d5f3ba9b0f1bd864"  # pragma: allowlist secret
            "ea46e30e2ea7f28fe838622cb5f663ee"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM04B-relevance/v5-token-probe.json": (
        1,
        (
            "156dd2648ca4f86f89b96d464a0ed0be"  # pragma: allowlist secret
            "c142312bf92e0fbce8dc6d3894413efd"  # pragma: allowlist secret
        ),
        (
            "0c3d8d4a7d6e67df6d0cd64405d51611"  # pragma: allowlist secret
            "9ce0ca644675b81376cf2dee8ef028db"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM04B-relevance/v6-evaluation.json": (
        2,
        (
            "57e292979442eb98a971ea70c0d63a84"  # pragma: allowlist secret
            "142ff5224b32ff8599471f02bf1321e0"  # pragma: allowlist secret
        ),
        (
            "1be665afaafe1e92b972018936b058f8"  # pragma: allowlist secret
            "e245cc76d684f436e3ec979601f6e126"  # pragma: allowlist secret
        ),
    ),
    "docs/verification/MEM04B-relevance/v6-token-probe.json": (
        1,
        (
            "a6a6a391b53cd27a25a7b0ec82594452"  # pragma: allowlist secret
            "776e196bbd0c235bf4277b59442975e3"  # pragma: allowlist secret
        ),
        (
            "a8fc97dbb037803c6c8559b856c3347e"  # pragma: allowlist secret
            "1e38c0870c8ccd808d9517ad22ae6742"  # pragma: allowlist secret
        ),
    ),
}


def reviewed_snapshot(path: str, batch: list[tuple[str, int, str, str, bool]]) -> bool:
    expected = REVIEWED_SNAPSHOTS.get(path)
    if expected is None or len(batch) != expected[0]:
        return False
    target = Path(path)
    try:
        if any(part.is_symlink() for part in (target, *target.parents)):
            return False
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected[1]:
            return False
    except OSError:
        return False
    encoded = json.dumps(sorted(batch), ensure_ascii=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest() == expected[2]


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate report key")
        result[key] = value
    return result


def unresolved(report: object) -> list[tuple[str, int, str]]:
    if not isinstance(report, dict) or not isinstance(report.get("results"), dict):
        raise ValueError("invalid report")
    try:
        profile_matches = hashlib.sha256(Path(PROFILE).read_bytes()).hexdigest() == PROFILE_SHA256
    except OSError:
        profile_matches = False
    failures: list[tuple[str, int, str]] = []
    for path, findings in report["results"].items():
        if not isinstance(path, str) or not isinstance(findings, list) or not findings:
            raise ValueError("invalid findings")
        batch: list[tuple[str, int, str, str, bool]] = []
        for finding in findings:
            if not isinstance(finding, dict):
                raise ValueError("invalid finding")
            line = finding.get("line_number")
            kind = finding.get("type")
            fingerprint = finding.get("hashed_secret")
            verified = finding.get("is_verified")
            if (
                type(line) is not int
                or line < 1
                or not isinstance(kind, str)
                or not isinstance(fingerprint, str)
                or finding.get("filename") != path
                or type(verified) is not bool
            ):
                raise ValueError("invalid finding binding")
            batch.append((path, line, kind, fingerprint, verified))
        if reviewed_snapshot(path, batch):
            continue
        for _, line, kind, fingerprint, verified in batch:
            if (
                path == PROFILE
                and profile_matches
                and kind == "Hex High Entropy String"
                and verified is False
                and (line, fingerprint) in PUBLIC_PINS
            ):
                continue
            failures.append((path, line, kind))
    return failures


def main() -> int:
    try:
        failures = unresolved(json.load(sys.stdin, object_pairs_hook=unique_object))
    except (ValueError, TypeError):
        print("Invalid secret scanner report; CI refused.", file=sys.stderr)
        return 1
    for path, line, kind in failures:
        print(f"{path}:{line}: {kind}", file=sys.stderr)
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
