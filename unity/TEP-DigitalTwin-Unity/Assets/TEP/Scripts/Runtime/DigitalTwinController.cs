using UnityEngine;

namespace TEP.DigitalTwin
{
    public sealed class DigitalTwinController : MonoBehaviour
    {
        [SerializeField] private PredictionSource source;
        [SerializeField] private DashboardPanel dashboard;
        [SerializeField] private EquipmentView[] equipment;
        private bool usesExternalSource;

        private void OnEnable()
        {
            if (source != null && !usesExternalSource) source.PredictionReceived += ApplyPrediction;
        }

        private void OnDisable()
        {
            if (source != null) source.PredictionReceived -= ApplyPrediction;
        }

        public void ApplyExternalPrediction(PredictionSnapshot prediction)
        {
            if (!usesExternalSource)
            {
                usesExternalSource = true;
                if (source != null)
                {
                    source.PredictionReceived -= ApplyPrediction;
                    source.enabled = false;
                }
            }
            ApplyPrediction(prediction);
        }

        public void ApplyPrediction(PredictionSnapshot prediction)
        {
            dashboard?.Apply(prediction);
            foreach (var view in equipment)
                view?.Apply(prediction);
        }
    }
}
