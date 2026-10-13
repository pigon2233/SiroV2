from siro.core.preferences import extract_explicit_preference


def test_extracts_only_explicit_owner_preferences() -> None:
    liked = extract_explicit_preference("我非常喜歡爵士樂")
    assert liked is not None
    assert (liked.subject, liked.polarity, liked.strength) == ("爵士樂", 1.0, 1.0)
    disliked = extract_explicit_preference("我不喜歡香菜。")
    assert disliked is not None
    assert (disliked.subject, disliked.polarity) == ("香菜", -1.0)
    assert extract_explicit_preference("他可能喜歡爵士樂") is None
    assert extract_explicit_preference("推薦我可能喜歡的音樂") is None
    assert extract_explicit_preference("我喜歡什麼音樂\uff1f只回答種類。") is None
