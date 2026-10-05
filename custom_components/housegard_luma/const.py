DOMAIN = "housegard_luma"
CONF_TUYA_ENTRY_ID = "tuya_entry_id"
CONF_GATEWAY_ID = "gateway_id"
LUMA_PRODUCT_ID = "s3x3xmgbeohtvm40"
DP_SUB_ADMIN = "sub_admin"
DP_ALARM_MSG = "alarm_msg"

INVENTORY_CODES = (DP_SUB_ADMIN, *(f"sub_admin{i}" for i in range(1, 8)))
# Verified Housegard Luma raw response IDs; SDK metadata may omit continuations.
INVENTORY_DP_CODES = {
    38: DP_SUB_ADMIN,
    104: "sub_admin1",
    105: "sub_admin2",
    106: "sub_admin3",
    107: "sub_admin4",
    108: "sub_admin5",
    109: "sub_admin6",
    110: "sub_admin7",
}
INVENTORY_QUERY = "Agc="  # RAW 02 07 at Manager.send_commands' JSON boundary.
INVENTORY_TIMEOUT = 15
INVENTORY_COOLDOWN = 30

# Controlled app Network Test Publish, 2026-09-29; opaque bytes 07 07 FF 03 3C.
NETWORK_TEST_COMMAND = "Bwf/Azw="

# Controlled app Sound Test Publish, 2026-09-29; observed target byte FF.
SOUND_TEST_COMMAND = "Bwf/Ag=="
