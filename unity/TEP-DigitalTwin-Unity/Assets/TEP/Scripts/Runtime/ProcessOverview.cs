using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace TEP.DigitalTwin
{
    /// <summary>Process-wide prediction display. Geometry is illustrative, not a process simulation.</summary>
    public sealed class ProcessOverview : MonoBehaviour
    {
        public DigitalTwinController controller;
        public TextAsset recordedPrediction;
        public bool showRecordedPreview;
        private PredictionSnapshot prediction;
        private Camera overviewCamera;
        private readonly List<Renderer> stateBands = new List<Renderer>();
        private Material steel, lightSteel, darkSteel, pipeMaterial, cyan, amber, floor, stateMaterial;
        private Font font;
        private float lastReceived;
        private bool recorded;
        private string connectionState = "connecting";
        private string sourceMode = "api";
        private string capturePath;
        private Color statusColor = new Color32(76, 175, 80, 255);
        private readonly Color ink = new Color32(229, 237, 245, 255);
        private readonly Color muted = new Color32(137, 159, 180, 255);
        private readonly Color accent = new Color32(73, 213, 218, 255);
        private readonly Color surface = new Color32(19, 30, 43, 255);

        private void Awake()
        {
            font = Resources.Load<Font>("NanumGothic-Regular");
            if (font == null) throw new InvalidOperationException("한글 UI 폰트가 없습니다.");
            Application.targetFrameRate = 30;
            BuildProcess();
        }

        private void Update()
        {
            // Preserve the layout and type proportions inside a resized WebGL canvas.
            var scale = Mathf.Min(Screen.width / 1920f, Screen.height / 1080f);
            var offsetX = (Screen.width - 1920f * scale) * .5f;
            var offsetY = (Screen.height - 1080f * scale) * .5f;
            overviewCamera.rect = new Rect((offsetX + 30 * scale) / Screen.width,
                (Screen.height - offsetY - 913 * scale) / Screen.height,
                1394 * scale / Screen.width, 719 * scale / Screen.height);
        }

        private IEnumerator Start()
        {
            controller.PredictionApplied += Receive;
            var args = Environment.GetCommandLineArgs();
            var snapshotPath = Arg(args, "-tepSnapshot");
            capturePath = Arg(args, "-tepCapture");
            if (!string.IsNullOrEmpty(snapshotPath))
            {
                recorded = true;
                controller.ApplyExternalPrediction(JsonUtility.FromJson<PredictionSnapshot>(File.ReadAllText(snapshotPath)));
            }
            else if (showRecordedPreview && recordedPrediction != null)
            {
                recorded = true;
                controller.ApplyExternalPrediction(JsonUtility.FromJson<PredictionSnapshot>(recordedPrediction.text));
            }
            if (!string.IsNullOrEmpty(capturePath))
            {
                for (var i = 0; i < 100; i++) yield return null;
                yield return new WaitForEndOfFrame();
                Directory.CreateDirectory(Path.GetDirectoryName(capturePath));
                ScreenCapture.CaptureScreenshot(capturePath);
                for (var i = 0; i < 30; i++) yield return null;
                Debug.Log("TEP_CAPTURE_COMPLETE " + capturePath);
                Application.Quit();
            }
        }

        private static string Arg(string[] args, string name)
        {
            var index = Array.IndexOf(args, name);
            return index >= 0 && index + 1 < args.Length ? args[index + 1] : null;
        }

        private void OnDestroy()
        {
            if (controller != null) controller.PredictionApplied -= Receive;
        }

        private void Receive(PredictionSnapshot snapshot)
        {
            prediction = snapshot;
            lastReceived = Time.realtimeSinceStartup;
            statusColor = snapshot.Status switch
            {
                ProcessStatus.CRITICAL => new Color32(242, 100, 111, 255),
                ProcessStatus.WARNING => new Color32(255, 156, 80, 255),
                ProcessStatus.CAUTION => new Color32(241, 199, 97, 255),
                _ => new Color32(84, 207, 157, 255),
            };
            stateMaterial.color = statusColor;
            if (stateMaterial.HasProperty("_BaseColor")) stateMaterial.SetColor("_BaseColor", statusColor);
            foreach (var band in stateBands) band.sharedMaterial = stateMaterial;
        }

        public void ApplyConnectionState(double receivedAtMs, string mode, string state)
        {
            var age = Math.Max(0, DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() - receivedAtMs) / 1000.0;
            lastReceived = Time.realtimeSinceStartup - (float)Math.Min(age, 86400);
            sourceMode = mode;
            connectionState = state;
            recorded = false;
        }

        public void RejectPrediction()
        {
            connectionState = "error";
        }

        private Material Material(string name, Color color, float metal = .1f)
        {
            var template = Resources.Load<Material>("ProcessSurface");
            var shader = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard");
            var result = template != null ? new Material(template) : new Material(shader);
            result.name = name;
            result.color = color;
            result.SetColor("_BaseColor", color);
            result.SetFloat("_Metallic", metal);
            result.SetFloat("_Smoothness", .35f);
            return result;
        }

        private GameObject Shape(PrimitiveType kind, string name, Vector3 position, Vector3 scale, Material material)
        {
            var item = GameObject.CreatePrimitive(kind);
            item.name = name;
            item.transform.SetParent(transform, false);
            item.transform.localPosition = position;
            item.transform.localScale = scale;
            item.GetComponent<Renderer>().sharedMaterial = material;
            var collider = item.GetComponent<Collider>();
            if (collider != null) Destroy(collider);
            return item;
        }

        private void Segment(string name, Vector3 a, Vector3 b, float radius, Material material)
        {
            var item = Shape(PrimitiveType.Cylinder, name, (a + b) * .5f,
                new Vector3(radius * 2, (b - a).magnitude * .5f, radius * 2), material);
            item.transform.up = (b - a).normalized;
        }

        private void Pipe(string name, float radius, Material material, params Vector3[] points)
        {
            for (var i = 1; i < points.Length; i++) Segment(name, points[i - 1], points[i], radius, material);
            foreach (var point in points) Shape(PrimitiveType.Sphere, name + " elbow", point, Vector3.one * radius * 2, material);
        }

        private void Ring(string name, Vector3 center, float radius, Material material)
        {
            const int steps = 32;
            var points = new Vector3[steps + 1];
            for (var i = 0; i <= steps; i++)
            {
                var angle = i * Mathf.PI * 2 / steps;
                points[i] = center + new Vector3(Mathf.Cos(angle) * radius, 0, Mathf.Sin(angle) * radius);
            }
            Pipe(name, .025f, material, points);
        }

        private void Vessel(string name, float x, float z, float height, float diameter)
        {
            Shape(PrimitiveType.Cube, name + " skid", new Vector3(x, .12f, z), new Vector3(diameter + .5f, .22f, diameter + .5f), darkSteel);
            Shape(PrimitiveType.Cylinder, name + " shell", new Vector3(x, height * .5f + .48f, z), new Vector3(diameter, height * .5f, diameter), steel);
            Shape(PrimitiveType.Sphere, name + " head", new Vector3(x, height + .48f, z), new Vector3(diameter, diameter * .4f, diameter), lightSteel);
            Shape(PrimitiveType.Sphere, name + " base", new Vector3(x, .48f, z), new Vector3(diameter, diameter * .35f, diameter), steel);
            foreach (var side in new[] { -1f, 1f })
            {
                Shape(PrimitiveType.Cube, name + " support", new Vector3(x + side * diameter * .3f, .35f, z), new Vector3(.12f, .6f, .18f), darkSteel);
                Shape(PrimitiveType.Cube, name + " ladder", new Vector3(x + diameter * .6f, height * .5f + .5f, z + side * .16f), new Vector3(.035f, height, .035f), darkSteel);
            }
            for (var y = .65f; y < height + .6f; y += .23f)
                Shape(PrimitiveType.Cube, name + " rung", new Vector3(x + diameter * .6f, y, z), new Vector3(.04f, .035f, .38f), lightSteel);
            var band = Shape(PrimitiveType.Cylinder, name + " process-state band", new Vector3(x, height * .55f + .5f, z), new Vector3(diameter + .025f, .065f, diameter + .025f), stateMaterial);
            stateBands.Add(band.GetComponent<Renderer>());
            Ring(name + " foundation", new Vector3(x, .24f, z), diameter * .75f, cyan);
        }

        private void Label(string title, string subtitle, Vector3 position)
        {
            var label = new GameObject(title + " label");
            label.transform.SetParent(transform, false);
            label.transform.localPosition = position;
            label.transform.rotation = overviewCamera.transform.rotation;
            var text = label.AddComponent<TextMesh>();
            text.font = font;
            text.fontSize = 54;
            text.characterSize = .075f;
            text.anchor = TextAnchor.MiddleCenter;
            text.alignment = TextAlignment.Center;
            text.text = title + "\n" + subtitle;
            text.color = ink;
            label.GetComponent<MeshRenderer>().sharedMaterial = text.font.material;
        }

        private void Arrow(Vector3 position, Vector3 direction, Material material)
        {
            var right = Vector3.Cross(direction.normalized, Vector3.up).normalized;
            Segment("flow direction", position - direction.normalized * .25f + right * .18f, position, .035f, material);
            Segment("flow direction", position - direction.normalized * .25f - right * .18f, position, .035f, material);
        }

        private void BuildProcess()
        {
            steel = Material("Brushed vessel alloy", new Color32(166, 188, 204, 255), .55f);
            lightSteel = Material("Vessel head", new Color32(196, 211, 220, 255), .5f);
            darkSteel = Material("Structural graphite", new Color32(43, 63, 78, 255), .5f);
            pipeMaterial = Material("Main process line", new Color32(56, 183, 190, 255), .35f);
            cyan = Material("Flow accent", accent);
            amber = Material("Recycle circuit", new Color32(233, 183, 82, 255), .3f);
            floor = Material("Process deck", new Color32(23, 38, 51, 255));
            stateMaterial = Material("Global process condition", new Color32(137, 159, 180, 255));

            var cameraObject = new GameObject("Process overview camera", typeof(Camera));
            cameraObject.transform.SetParent(transform, false);
            overviewCamera = cameraObject.GetComponent<Camera>();
            cameraObject.tag = "MainCamera";
            cameraObject.transform.localPosition = new Vector3(12, 14, -21);
            cameraObject.transform.LookAt(transform.TransformPoint(new Vector3(.2f, 1.2f, .5f)));
            overviewCamera.orthographic = true;
            overviewCamera.orthographicSize = 7.4f;
            overviewCamera.backgroundColor = new Color32(12, 21, 31, 255);
            overviewCamera.clearFlags = CameraClearFlags.SolidColor;
            overviewCamera.rect = new Rect(.016f, .155f, .726f, .665f);
            overviewCamera.nearClipPlane = .1f;
            overviewCamera.farClipPlane = 80;
            var key = new GameObject("Soft industrial key", typeof(Light));
            key.transform.SetParent(transform, false);
            key.transform.rotation = Quaternion.Euler(48, -25, 0);
            key.GetComponent<Light>().type = LightType.Directional;
            key.GetComponent<Light>().intensity = 1.3f;
            key.GetComponent<Light>().shadows = LightShadows.Soft;
            var fill = new GameObject("Cool fill", typeof(Light));
            fill.transform.SetParent(transform, false);
            fill.transform.rotation = Quaternion.Euler(65, 145, 0);
            fill.GetComponent<Light>().type = LightType.Directional;
            fill.GetComponent<Light>().color = new Color(.55f, .78f, 1f);
            fill.GetComponent<Light>().intensity = .7f;
            RenderSettings.ambientLight = new Color(.43f, .51f, .62f);

            Shape(PrimitiveType.Cube, "Process platform", new Vector3(0, -.16f, .7f), new Vector3(20, .3f, 9), floor);
            for (var x = -10; x <= 10; x++) Segment("deck grid", new Vector3(x, .004f, -3.8f), new Vector3(x, .004f, 5.2f), .008f, darkSteel);
            for (var z = -3; z <= 5; z++) Segment("deck grid", new Vector3(-10, .004f, z), new Vector3(10, .004f, z), .008f, darkSteel);
            Pipe("platform edge", .028f, pipeMaterial, new Vector3(-10, .02f, -3.8f), new Vector3(10, .02f, -3.8f), new Vector3(10, .02f, 5.2f), new Vector3(-10, .02f, 5.2f), new Vector3(-10, .02f, -3.8f));

            Vessel("R-101 reactor", -5.4f, 0, 3.7f, 1.9f);
            Shape(PrimitiveType.Cylinder, "Agitator drive", new Vector3(-5.4f, 4.65f, 0), new Vector3(.45f, .3f, .45f), darkSteel);
            Ring("Reactor service rail", new Vector3(-5.4f, 4.25f, 0), 1.25f, lightSteel);
            Vessel("V-101 separator", 1.7f, 0, 2.8f, 1.6f);
            Vessel("T-101 stripper", 6.3f, 0, 4.5f, 1.15f);
            for (var y = 1.2f; y < 4.8f; y += .7f) Ring("column tray seam", new Vector3(6.3f, y, 0), .585f, darkSteel);

            var cooler = Shape(PrimitiveType.Cylinder, "E-101 condenser", new Vector3(-1.7f, 1.8f, 0), new Vector3(1.15f, 1.2f, 1.15f), steel);
            cooler.transform.localRotation = Quaternion.Euler(0, 0, 90);
            for (var x = -2.65f; x < -.65f; x += .28f)
            {
                var fin = Shape(PrimitiveType.Cylinder, "Condenser fin", new Vector3(x, 1.8f, 0), new Vector3(1.35f, .028f, 1.35f), darkSteel);
                fin.transform.localRotation = Quaternion.Euler(0, 0, 90);
            }
            foreach (var x in new[] { -2.4f, -1f }) Shape(PrimitiveType.Cube, "Condenser cradle", new Vector3(x, .7f, 0), new Vector3(.25f, 1.1f, .8f), darkSteel);
            Shape(PrimitiveType.Cube, "Condenser skid", new Vector3(-1.7f, .12f, 0), new Vector3(2.9f, .22f, 1.8f), darkSteel);
            Ring("Condenser foundation", new Vector3(-1.7f, .24f, 0), 1.3f, cyan);

            Shape(PrimitiveType.Cube, "Recycle skid", new Vector3(1.6f, .15f, 3.55f), new Vector3(2.5f, .3f, 1.9f), darkSteel);
            var compressor = Shape(PrimitiveType.Cylinder, "C-101 compressor", new Vector3(1.4f, 1.15f, 3.55f), new Vector3(1.25f, .45f, 1.25f), steel);
            compressor.transform.localRotation = Quaternion.Euler(90, 0, 0);
            Shape(PrimitiveType.Cube, "Compressor motor", new Vector3(2.25f, .8f, 3.55f), new Vector3(.85f, .85f, 1.1f), darkSteel);

            Pipe("Feed A", .09f, pipeMaterial, new Vector3(-9.1f, .8f, -.6f), new Vector3(-6.55f, .8f, -.6f), new Vector3(-6.55f, 2.1f, -.6f), new Vector3(-5.4f, 2.1f, -.6f));
            Pipe("Feed B", .09f, pipeMaterial, new Vector3(-9.1f, .8f, .35f), new Vector3(-7.2f, .8f, .35f), new Vector3(-7.2f, 2.1f, .35f), new Vector3(-5.4f, 2.1f, .35f));
            Pipe("Reaction output", .1f, pipeMaterial, new Vector3(-4.4f, 1.65f, 0), new Vector3(-3.4f, 1.65f, 0), new Vector3(-3.4f, 1.8f, 0), new Vector3(-2.9f, 1.8f, 0));
            Pipe("Condensed feed", .1f, pipeMaterial, new Vector3(-.5f, 1.8f, 0), new Vector3(.9f, 1.8f, 0));
            Pipe("Liquid feed", .1f, pipeMaterial, new Vector3(1.7f, .8f, -.8f), new Vector3(1.7f, .8f, -1.6f), new Vector3(5.4f, .8f, -1.6f), new Vector3(5.4f, 1.9f, -1.6f), new Vector3(6.3f, 1.9f, -.5f));
            Pipe("Product", .1f, pipeMaterial, new Vector3(6.3f, .75f, .5f), new Vector3(7.5f, .75f, .5f), new Vector3(9.1f, .75f, .5f));
            Pipe("Recycle vapor", .075f, amber, new Vector3(1.7f, 3.35f, 0), new Vector3(1.7f, 3.35f, 3.55f), new Vector3(1.7f, 1.3f, 3.55f));
            Pipe("Recycle return", .075f, amber, new Vector3(.95f, 1.3f, 3.55f), new Vector3(-5.4f, 1.3f, 3.55f), new Vector3(-5.4f, 3.6f, 3.55f), new Vector3(-5.4f, 3.6f, .8f));
            Arrow(new Vector3(-7.8f, .8f, -.6f), Vector3.right, cyan);
            Arrow(new Vector3(-3.8f, 1.65f, 0), Vector3.right, cyan);
            Arrow(new Vector3(.2f, 1.8f, 0), Vector3.right, cyan);
            Arrow(new Vector3(3.8f, .8f, -1.6f), Vector3.right, cyan);
            Arrow(new Vector3(8.4f, .75f, .5f), Vector3.right, cyan);
            Arrow(new Vector3(-2.9f, 1.3f, 3.55f), Vector3.left, amber);

            Label("R-101", "반응기", new Vector3(-5.4f, 5.8f, 0));
            Label("E-101", "응축·냉각기", new Vector3(-2.1f, 4.6f, -.2f));
            Label("V-101", "분리기", new Vector3(1.7f, 4.4f, -.4f));
            Label("T-101", "정제기", new Vector3(6.3f, 6.2f, 0));
            Label("C-101", "재순환 압축기", new Vector3(2.5f, 4.9f, 3.55f));
            Label("원료 투입", "A + B + C + D", new Vector3(-8.7f, 1.8f, -.5f));
            Label("제품 생산", "G + H", new Vector3(8.6f, 1.8f, .5f));
        }

        private GUIStyle Style(int size, Color color, FontStyle weight = FontStyle.Normal, TextAnchor alignment = TextAnchor.UpperLeft)
        {
            return new GUIStyle(GUI.skin.label) { font = font, fontSize = size, normal = { textColor = color }, fontStyle = weight, alignment = alignment, padding = new RectOffset(0, 0, 0, 0), wordWrap = true };
        }

        private void Box(float x, float y, float width, float height, Color color)
        {
            var old = GUI.color;
            GUI.color = color;
            GUI.DrawTexture(new Rect(x, y, width, height), Texture2D.whiteTexture);
            GUI.color = old;
        }

        private void Text(float x, float y, float width, float height, string value, int size, Color color, bool bold = false, TextAnchor alignment = TextAnchor.UpperLeft)
        {
            GUI.Label(new Rect(x, y, width, height), value, Style(size, color, bold ? FontStyle.Bold : FontStyle.Normal, alignment));
        }

        private void OnGUI()
        {
            var prior = GUI.matrix;
            var scale = Mathf.Min(Screen.width / 1920f, Screen.height / 1080f);
            var offsetX = (Screen.width - 1920f * scale) * .5f;
            var offsetY = (Screen.height - 1080f * scale) * .5f;
            Box(0, 0, Screen.width, offsetY, Color.black);
            Box(0, Screen.height - offsetY, Screen.width, offsetY, Color.black);
            Box(0, 0, offsetX, Screen.height, Color.black);
            Box(Screen.width - offsetX, 0, offsetX, Screen.height, Color.black);
            GUI.matrix = Matrix4x4.TRS(new Vector3(offsetX, offsetY, 0), Quaternion.identity, new Vector3(scale, scale, 1));
            // Draw only outside the camera viewport; its 3D image remains unobscured.
            var background = new Color32(12, 21, 31, 255);
            Box(0, 0, 1920, 194, background);
            Box(0, 194, 30, 719, background);
            Box(1425, 0, 495, 1080, background);
            Box(0, 913, 1920, 167, background);
            Box(30, 24, 6, 63, accent);
            Text(52, 23, 650, 45, "TEP / 공정 디지털트윈", 32, ink, true);
            Text(52, 68, 800, 30, "화학공정 모니터링 · AI 기반 예지보전", 18, muted);
            var source = prediction == null ? "웹 / API 데이터 대기" : recorded ? "기록된 예측 데이터" : sourceMode == "mock" ? "모의 데이터" : controller.UsesExternalSource ? "웹 / API 예측 데이터" : "모의 데이터";
            Box(1070, 33, 330, 40, surface);
            Text(1086, 39, 300, 30, source, 16, recorded ? muted : accent, true);
            Box(30, 112, 1394, 1, new Color32(41, 61, 79, 255));
            Text(40, 130, 500, 35, "01   공정 전체 보기", 18, accent, true);
            Text(790, 131, 615, 32, "공정 흐름을 표현한 모형 / 공정 전체 예측", 17, muted, false, TextAnchor.UpperRight);

            Box(1450, 24, 440, 1020, surface);
            var age = Time.realtimeSinceStartup - lastReceived;
            var badge = recorded ? "기록 화면 · 실시간 아님" : connectionState == "error" ? "연결 오류 · 마지막 예측 유지" : prediction == null ? "데이터 수신 대기" : connectionState == "paused" ? "화면 갱신 일시정지" : sourceMode == "mock" || !controller.UsesExternalSource ? "모의 데이터 재생 중" : connectionState == "stale" || age > 15 ? "데이터 갱신 지연 · 마지막 예측" : "데이터 수신 중";
            Text(1478, 47, 386, 28, "02   공정 상태 모니터링", 17, accent, true);
            Text(1478, 90, 386, 32, badge, 16, muted);
            Box(1478, 135, 5, 86, prediction == null ? muted : statusColor);
            Text(1499, 135, 360, 58, prediction == null ? "대기 중" : KoreanUi.Status(prediction.Status), 42, prediction == null ? muted : statusColor, true);
            Text(1499, 192, 355, 28, "공정 전체 상태", 17, muted);
            Box(1478, 241, 384, 1, new Color32(49, 68, 83, 255));
            Text(1478, 263, 384, 28, "예측 잔여수명", 15, muted, true);
            Text(1478, 300, 384, 70, prediction == null ? "--" : prediction.rul.hours.ToString("0.00") + " 시간", 46, ink, true);
            Text(1478, 374, 384, 27, "각 시간 범위 내 고장 위험 확률", 17, muted);
            RiskRow(1478, 423, "4시간 이내", prediction?.risk?.failure_within_4h);
            RiskRow(1478, 513, "2시간 이내", prediction?.risk?.failure_within_2h);
            RiskRow(1478, 603, "1시간 이내", prediction?.risk?.failure_within_1h);
            Box(1478, 694, 384, 1, new Color32(49, 68, 83, 255));
            Text(1478, 716, 384, 28, "주요 위험 요인 / 모델 설명", 15, muted, true);
            if (prediction?.top_risk_factors != null && prediction.top_risk_factors.Length > 0)
            {
                for (var i = 0; i < Math.Min(3, prediction.top_risk_factors.Length); i++)
                {
                    var factor = prediction.top_risk_factors[i];
                    Text(1478, 756 + i * 52, 310, 28, (i + 1) + "  " + KoreanUi.Feature(factor.source_feature ?? factor.feature), 17, ink);
                    Text(1788, 756 + i * 52, 74, 28, factor.shap_value.ToString("+0.00;-0.00"), 17, accent, true, TextAnchor.UpperRight);
                    Text(1500, 781 + i * 52, 360, 23, KoreanUi.Transform(factor), 13, muted);
                }
            }
            else Text(1478, 761, 384, 62, "예측 데이터가 제공하는 주요 위험 요인을 표시합니다.", 17, muted);
            Box(1478, 934, 384, 1, new Color32(49, 68, 83, 255));
            Text(1478, 953, 384, 24, (prediction == null ? "선택된 데이터 없음" : KoreanUi.Trajectory(prediction.trajectory_key)) + " / " + (prediction?.model_version ?? "--"), 17, ink);
            Text(1478, 984, 384, 24, "공정 경과시간  " + (prediction == null ? "--" : prediction.timestamp_hours.ToString("0.00") + " 시간"), 16, muted);

            Box(40, 178, 19, 4, accent);
            Text(70, 169, 190, 30, "주 공정 배관", 16, muted);
            Box(257, 178, 19, 4, new Color32(233, 183, 82, 255));
            Text(287, 169, 210, 30, "기체 재순환 배관", 16, muted);
            Text(905, 169, 500, 30, "설비 색상 띠 = 공정 전체 상태", 16, muted, false, TextAnchor.UpperRight);

            Box(40, 933, 1362, 1, new Color32(41, 61, 79, 255));
            var names = new[] { "원료 투입", "반응", "응축·냉각", "분리", "정제", "제품 생산" };
            var tags = new[] { "A / B / C / D", "R-101", "E-101", "V-101", "T-101", "G / H" };
            for (var i = 0; i < names.Length; i++)
            {
                var x = 43 + i * 230;
                Text(x, 950, 195, 31, names[i], 18, ink, true);
                Text(x, 983, 195, 25, tags[i], 15, muted);
                if (i < names.Length - 1) Text(x + 190, 958, 32, 30, "→", 22, accent);
            }
            Text(43, 1034, 1359, 27, "공정 전체의 잔여수명·고장 위험을 예측합니다. · 설비별 고장 위치를 뜻하지 않습니다. · 모형은 기획의 공정 흐름을 표현합니다.", 15, muted);
            GUI.matrix = prior;
        }

        private void RiskRow(float x, float y, string label, RiskEntry risk)
        {
            Text(x, y, 220, 27, label, 17, ink, true);
            Text(x + 232, y - 3, 152, 35, risk == null ? "--" : (risk.score * 100).ToString("0.0") + "%", 25, risk == null ? muted : statusColor, true, TextAnchor.UpperRight);
            Box(x, y + 37, 384, 6, new Color32(41, 61, 79, 255));
            if (risk != null)
            {
                Box(x, y + 37, Mathf.Clamp01(risk.score) * 384, 6, statusColor);
                Box(x + Mathf.Clamp01(risk.threshold) * 384, y + 32, 2, 16, ink);
                Text(x, y + 53, 384, 24, "판정 기준 " + (risk.threshold * 100).ToString("0.0") + "%   /   " + (risk.alert ? "위험 판정" : "기준 미만"), 14, muted);
            }
        }
    }
}
