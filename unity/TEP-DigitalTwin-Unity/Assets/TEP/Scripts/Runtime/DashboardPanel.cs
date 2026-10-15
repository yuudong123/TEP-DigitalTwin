using UnityEngine;
using UnityEngine.UI;

namespace TEP.DigitalTwin
{
    public sealed class DashboardPanel : MonoBehaviour
    {
        [SerializeField] private Text statusText;
        [SerializeField] private Text rulText;
        [SerializeField] private Text trajectoryText;
        [SerializeField] private Text fourHourText;
        [SerializeField] private Text twoHourText;
        [SerializeField] private Text oneHourText;
        [SerializeField] private Image statusIndicator;

        private void Awake()
        {
            var koreanFont = Resources.Load<Font>("NanumGothic-Regular");
            foreach (var text in GetComponentsInChildren<Text>()) text.font = koreanFont;
            statusText.text = "대기 중";
            rulText.text = "잔여수명  -- 시간";
            trajectoryText.text = "데이터 수신 대기";
            foreach (var entry in new[] { ("Title", "TEP 공정 디지털트윈"), ("RiskTitle", "고장 위험"), ("Source", "예측 데이터") })
            {
                var child = transform.Find(entry.Item1);
                if (child != null) child.GetComponent<Text>().text = entry.Item2;
            }
            SetRisk(fourHourText, "4시간 이내", null);
            SetRisk(twoHourText, "2시간 이내", null);
            SetRisk(oneHourText, "1시간 이내", null);
        }

        public void Apply(PredictionSnapshot prediction)
        {
            statusText.text = KoreanUi.Status(prediction.Status);
            rulText.text = $"잔여수명  {prediction.rul?.hours ?? 0f:0.00} 시간";
            trajectoryText.text = $"{KoreanUi.Trajectory(prediction.trajectory_key)}  |  {prediction.timestamp_hours:0.00} 시간";
            SetRisk(fourHourText, "4시간 이내", prediction.risk?.failure_within_4h);
            SetRisk(twoHourText, "2시간 이내", prediction.risk?.failure_within_2h);
            SetRisk(oneHourText, "1시간 이내", prediction.risk?.failure_within_1h);
            statusIndicator.color = StatusColor(prediction.Status);
        }

        private static void SetRisk(Text target, string label, RiskEntry risk)
        {
            target.text = risk == null
                ? $"{label}  --"
                : $"{label}  {risk.score:P1}  {(risk.alert ? "위험" : "기준 미만")}";
        }

        private static Color StatusColor(ProcessStatus status) => status switch
        {
            ProcessStatus.CAUTION => new Color32(0xF5, 0xA6, 0x23, 0xFF),
            ProcessStatus.WARNING => new Color32(0xFF, 0x7A, 0x00, 0xFF),
            ProcessStatus.CRITICAL => new Color32(0xE6, 0x39, 0x46, 0xFF),
            _ => new Color32(0x4C, 0xAF, 0x50, 0xFF),
        };
    }
}
