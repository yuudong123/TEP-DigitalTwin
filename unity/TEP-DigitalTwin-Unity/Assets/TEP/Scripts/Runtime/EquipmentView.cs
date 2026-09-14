using UnityEngine;

namespace TEP.DigitalTwin
{
    public enum RiskBinding { Overall, FourHour, TwoHour, OneHour }

    public sealed class EquipmentView : MonoBehaviour
    {
        [SerializeField] private string displayName = "Equipment";
        [SerializeField] private RiskBinding riskBinding;
        [SerializeField] private StatusPalette palette;
        [SerializeField] private Renderer[] coloredRenderers;
        [SerializeField] private TextMesh label;

        public void Apply(PredictionSnapshot prediction)
        {
            var status = ResolveStatus(prediction);
            var material = palette != null ? palette.Get(status) : null;
            if (material != null)
            {
                foreach (var target in coloredRenderers)
                    if (target != null) target.sharedMaterial = material;
            }

            if (label != null)
            {
                label.text = $"{displayName}\n{status}";
                label.color = Color.white;
            }
        }

        private ProcessStatus ResolveStatus(PredictionSnapshot prediction)
        {
            if (riskBinding == RiskBinding.Overall) return prediction.Status;
            var risk = riskBinding switch
            {
                RiskBinding.FourHour => prediction.risk?.failure_within_4h,
                RiskBinding.TwoHour => prediction.risk?.failure_within_2h,
                _ => prediction.risk?.failure_within_1h,
            };
            if (risk == null) return ProcessStatus.NORMAL;
            var ratio = risk.threshold > 0f ? risk.score / risk.threshold : 0f;
            if (risk.alert || ratio >= 1f) return ProcessStatus.CRITICAL;
            if (ratio >= 0.8f) return ProcessStatus.WARNING;
            if (ratio >= 0.6f) return ProcessStatus.CAUTION;
            return ProcessStatus.NORMAL;
        }
    }
}
