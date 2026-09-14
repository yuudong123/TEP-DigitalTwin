using UnityEngine;

namespace TEP.DigitalTwin
{
    public sealed class DigitalTwinController : MonoBehaviour
    {
        [SerializeField] private PredictionSource source;
        [SerializeField] private DashboardPanel dashboard;
        [SerializeField] private EquipmentView[] equipment;

        private void OnEnable()
        {
            if (source != null) source.PredictionReceived += Apply;
        }

        private void OnDisable()
        {
            if (source != null) source.PredictionReceived -= Apply;
        }

        private void Apply(PredictionSnapshot prediction)
        {
            dashboard?.Apply(prediction);
            foreach (var view in equipment)
                view?.Apply(prediction);
        }
    }
}
