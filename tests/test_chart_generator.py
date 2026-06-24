from slideforge.tools.chart_generator import ChartData


def test_chart_data_accepts_list_rows_as_category_series_data():
    data = ChartData(
        title="Comparison",
        data=[
            {"category": "A", "Curry": 4, "James": 4},
            {"category": "B", "Curry": 2, "James": 3},
        ],
        data_source="test",
    )

    assert data.data["categories"] == ["A", "B"]
    assert data.data["series"] == [
        {"name": "Curry", "values": [4, 2]},
        {"name": "James", "values": [4, 3]},
    ]
    assert data.data["headers"] == ["category", "Curry", "James"]
