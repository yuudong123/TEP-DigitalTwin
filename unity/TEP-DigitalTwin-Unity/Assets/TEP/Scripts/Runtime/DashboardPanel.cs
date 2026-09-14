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

        public void Apply(PredictionSnapshot prediction)
        {
            statusText.text = prediction.status;
            rulText.text = $"RUL  {prediction.rul?.hours ?? 0f:0.00} h";
            trajectoryText.text = $"{prediction.trajectory_key}  |  t={prediction.timestamp_hours:0.00} h";
            SetRisk(fourHourText, "4 HOUR", prediction.risk?.failure_within_4h);
            SetRisk(twoHourText, "2 HOUR", prediction.risk?.failure_within_2h);
            SetRisk(oneHourText, "1 HOUR", prediction.risk?.failure_within_1h);
            statusIndicator.color = StatusColor(prediction.Status);
        }

        private static void SetRisk(Text target, string label, RiskEntry risk)
        {
            target.text = risk == null
                ? $"{label}  --"
                : $"{label}  {risk.score:P1}  {(risk.alert ? "ALERT" : "SAFE")}";
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
