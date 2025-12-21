import nbtlib
from nbtlib.tag import Byte, Compound, Double, Int, List, String


def convert_to_nbt(value):
    """
    將 JSON 字串解析並轉換為 NBT 結構
    """
    if isinstance(value, dict):
        return Compound({k: convert_to_nbt(v) for k, v in value.items()})
    elif isinstance(value, list):
        return List[Compound]([convert_to_nbt(v) for v in value])
    elif isinstance(value, str):
        return String(value)
    elif isinstance(value, int):
        return Int(value)
    elif isinstance(value, float):
        return Double(value)
    elif isinstance(value, bool):
        return Byte(1 if value else 0)
    else:
        raise ValueError(f"Unsupported data type: {type(value)}")


def create_frame_structure(filename: str, raw_json, data_version: int = 3465):
    """
    filename: 輸出的檔案名稱 (例如 "frame_001.nbt")
    frame_json_string: 您那串巨大的 JSON 像素文字
    data_version: Minecraft 版本號 (3465 是 1.20.1，這很重要，舊版本號可能導致讀取失敗)
    """

    # 1. 定義 Marker 實體
    # 這就是我們用來存放數據的載體
    marker_entity = Compound(
        {
            "pos": List[Double]([0.5, 0.5, 0.5]),  # 實體位於結構中心
            "blockPos": List[Int]([0, 0, 0]),  # 對應的方塊座標
            "nbt": Compound(
                {
                    "id": String("minecraft:marker"),  # 實體類型
                    "Tags": List[String](["video_player", "frame_data"]),
                    # --- 關鍵部分 ---
                    # 我們在 marker 身上自定義一個 "frame" 標籤來存文字
                    "data": Compound({"frame": List(convert_to_nbt(raw_json))}),
                    # ---------------
                }
            ),
        }
    )

    # 2. 定義結構檔案 (Structure Format)
    # 這是 Minecraft 結構方塊的標準格式，必須包含 size, entities, blocks, palette 等
    structure_file = Compound(
        {
            "size": List[Int]([1, 1, 1]),  # 結構大小 1x1x1
            "entities": List[Compound]([marker_entity]),
            "blocks": List[Compound]([]),  # 我們不需要方塊，所以留空
            "palette": List[Compound](
                [Compound({"Name": String("minecraft:air")})]  # 即使沒有方塊，通常也需要一個空的調色盤定義
            ),
            "DataVersion": Int(data_version),  # 這一行非常重要！
        }
    )

    # 3. 儲存檔案 (必須使用 Gzip 壓縮)
    file = nbtlib.File(structure_file)
    file.save(filename, gzipped=True)
    print(f"已生成: {filename}")


if __name__ == "__main__":
    # --- 使用範例 ---
    raw_json = [{"text": ""}, {"text": "█", "color": "#FF0000"}, {"text": "█", "color": "#00FF00"}]

    # 生成 frame001.nbt
    create_frame_structure("frame_001.nbt", raw_json)
