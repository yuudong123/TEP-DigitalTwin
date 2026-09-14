using UnityEngine;

namespace TEP.DigitalTwin
{
    [CreateAssetMenu(menuName = "TEP/Status Palette", fileName = "StatusPalette")]
    public sealed class StatusPalette : ScriptableObject
    {
        public Material normal;
        public Material caution;
        public Material warning;
        public Material critical;

        public Material Get(ProcessStatus status)
        {
            return status switch
            {
                ProcessStatus.CAUTION => caution,
                ProcessStatus.WARNING => warning,
                ProcessStatus.CRITICAL => critical,
                _ => normal,
            };
        }
    }
}
