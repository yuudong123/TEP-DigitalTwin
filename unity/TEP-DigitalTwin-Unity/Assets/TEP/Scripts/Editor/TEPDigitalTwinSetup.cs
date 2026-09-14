#if UNITY_EDITOR
using System.Collections.Generic;
using System.IO;
using System.Linq;
using TEP.DigitalTwin;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace TEP.Editor
{
    public static class TEPDigitalTwinSetup
    {
        private const string Root = "Assets/TEP";
        private const string Generated = Root + "/Generated";
        private const string Materials = Generated + "/Materials";
        private const string Prefabs = Generated + "/Prefabs";
        private const string Scenes = Root + "/Scenes";

        [MenuItem("TEP Digital Twin/Generate Demo (Prefabs + Scene)")]
        public static void Generate()
        {
            EnsureFolders();
            var palette = CreatePalette();
            var equipmentBase = CreateEquipmentBase(palette);
            var reactor = CreateEquipmentVariant(equipmentBase, palette, "Reactor", RiskBinding.Overall, BuildReactor);
            var separator = CreateEquipmentVariant(equipmentBase, palette, "Separator", RiskBinding.FourHour, BuildSeparator);
            var compressor = CreateEquipmentVariant(equipmentBase, palette, "Compressor", RiskBinding.TwoHour, BuildCompressor);
            var stripper = CreateEquipmentVariant(equipmentBase, palette, "Stripper", RiskBinding.OneHour, BuildStripper);
            var processLine = CreateProcessLine(reactor, separator, compressor, stripper);
            var dashboard = CreateDashboardPrefab();
            var runtime = CreateRuntimePrefab();
            var environment = CreateEnvironmentPrefab();
            CreateDemoScene(processLine, dashboard, runtime, environment);
            ValidateGeneratedAssets();
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log("TEP Digital Twin demo generated: Assets/TEP/Scenes/TEPDigitalTwinDemo.unity");
        }

        [MenuItem("TEP Digital Twin/Build WebGL for Web Dashboard")]
        public static void BuildWebGL()
        {
            var scenePath = $"{Scenes}/TEPDigitalTwinDemo.unity";
            if (!File.Exists(scenePath))
                throw new FileNotFoundException("Generate the demo scene before building WebGL.", scenePath);

            var outputPath = Path.GetFullPath(Path.Combine(
                Application.dataPath, "..", "..", "..", "web", "public", "unity"));
            Directory.CreateDirectory(outputPath);

            var previousCompression = PlayerSettings.WebGL.compressionFormat;
            try
            {
                // Plain files work in Vite and simple static servers without custom encoding headers.
                PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Disabled;
                var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
                {
                    scenes = new[] { scenePath },
                    locationPathName = outputPath,
                    target = BuildTarget.WebGL,
                    options = BuildOptions.None,
                });
                if (report.summary.result != BuildResult.Succeeded)
                    throw new InvalidDataException($"WebGL build failed: {report.summary.result}");
                Debug.Log($"TEP WebGL build ready for Vite: {outputPath}");
            }
            finally
            {
                PlayerSettings.WebGL.compressionFormat = previousCompression;
            }
        }

        private static void EnsureFolders()
        {
            EnsureFolder("Assets", "TEP");
            EnsureFolder(Root, "Generated");
            EnsureFolder(Generated, "Materials");
            EnsureFolder(Generated, "Prefabs");
            EnsureFolder(Root, "Scenes");
        }

        private static void EnsureFolder(string parent, string name)
        {
            var path = $"{parent}/{name}";
            if (!AssetDatabase.IsValidFolder(path)) AssetDatabase.CreateFolder(parent, name);
        }

        private static StatusPalette CreatePalette()
        {
            var palettePath = $"{Generated}/StatusPalette.asset";
            var oldPalette = AssetDatabase.LoadAssetAtPath<StatusPalette>(palettePath);
            if (oldPalette != null) AssetDatabase.DeleteAsset(palettePath);

            var palette = ScriptableObject.CreateInstance<StatusPalette>();
            palette.normal = CreateMaterial("Status_NORMAL", new Color32(0x4C, 0xAF, 0x50, 0xFF));
            palette.caution = CreateMaterial("Status_CAUTION", new Color32(0xF5, 0xA6, 0x23, 0xFF));
            palette.warning = CreateMaterial("Status_WARNING", new Color32(0xFF, 0x7A, 0x00, 0xFF));
            palette.critical = CreateMaterial("Status_CRITICAL", new Color32(0xE6, 0x39, 0x46, 0xFF));
            AssetDatabase.CreateAsset(palette, palettePath);
            return palette;
        }

        private static Material CreateMaterial(string name, Color color)
        {
            var path = $"{Materials}/{name}.mat";
            if (AssetDatabase.LoadAssetAtPath<Material>(path) != null) AssetDatabase.DeleteAsset(path);
            var shader = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard");
            var material = new Material(shader) { name = name, color = color };
            material.SetColor("_BaseColor", color);
            material.SetFloat("_Smoothness", 0.55f);
            AssetDatabase.CreateAsset(material, path);
            return material;
        }

        private static GameObject CreateEquipmentBase(StatusPalette palette)
        {
            var root = new GameObject("EquipmentBase");
            var bodyRoot = new GameObject("Body");
            bodyRoot.transform.SetParent(root.transform, false);
            var pedestal = Primitive(PrimitiveType.Cylinder, "Pedestal", bodyRoot.transform,
                new Vector3(0, 0.15f, 0), new Vector3(1.7f, 0.15f, 1.7f));
            pedestal.GetComponent<Renderer>().sharedMaterial = CreateMaterial("Equipment_Frame", new Color(0.14f, 0.18f, 0.23f));

            var labelObject = new GameObject("WorldLabel");
            labelObject.transform.SetParent(root.transform, false);
            labelObject.transform.localPosition = new Vector3(0, 3.8f, 0);
            labelObject.transform.localRotation = Quaternion.Euler(20, 180, 0);
            var label = labelObject.AddComponent<TextMesh>();
            label.text = "EQUIPMENT\nNORMAL";
            label.anchor = TextAnchor.MiddleCenter;
            label.alignment = TextAlignment.Center;
            label.fontSize = 36;
            label.characterSize = 0.075f;
            label.color = Color.white;

            var view = root.AddComponent<EquipmentView>();
            ConfigureView(view, "Equipment", RiskBinding.Overall, palette,
                new[] { pedestal.GetComponent<Renderer>() }, label);
            var path = $"{Prefabs}/EquipmentBase.prefab";
            var prefab = PrefabUtility.SaveAsPrefabAsset(root, path);
            Object.DestroyImmediate(root);
            return prefab;
        }

        private delegate void EquipmentBuilder(Transform parent, Material frame, List<Renderer> colored);

        private static GameObject CreateEquipmentVariant(GameObject basePrefab, StatusPalette palette,
            string displayName, RiskBinding binding, EquipmentBuilder builder)
        {
            var instance = (GameObject)PrefabUtility.InstantiatePrefab(basePrefab);
            instance.name = displayName;
            var body = instance.transform.Find("Body");
            var renderers = new List<Renderer>();
            var frame = AssetDatabase.LoadAssetAtPath<Material>($"{Materials}/Equipment_Frame.mat");
            builder(body, frame, renderers);
            var view = instance.GetComponent<EquipmentView>();
            ConfigureView(view, displayName, binding, palette, renderers.ToArray(),
                instance.transform.Find("WorldLabel").GetComponent<TextMesh>());
            var path = $"{Prefabs}/{displayName}.prefab";
            if (AssetDatabase.LoadAssetAtPath<GameObject>(path) != null) AssetDatabase.DeleteAsset(path);
            var prefab = PrefabUtility.SaveAsPrefabAsset(instance, path);
            Object.DestroyImmediate(instance);
            return prefab;
        }

        private static void ConfigureView(EquipmentView view, string name, RiskBinding binding,
            StatusPalette palette, Renderer[] renderers, TextMesh label)
        {
            var serialized = new SerializedObject(view);
            serialized.FindProperty("displayName").stringValue = name;
            serialized.FindProperty("riskBinding").enumValueIndex = (int)binding;
            serialized.FindProperty("palette").objectReferenceValue = palette;
            serialized.FindProperty("label").objectReferenceValue = label;
            var targets = serialized.FindProperty("coloredRenderers");
            targets.arraySize = renderers.Length;
            for (var i = 0; i < renderers.Length; i++)
                targets.GetArrayElementAtIndex(i).objectReferenceValue = renderers[i];
            serialized.ApplyModifiedPropertiesWithoutUndo();
        }

        private static void BuildReactor(Transform parent, Material frame, List<Renderer> colored)
        {
            var tank = Primitive(PrimitiveType.Cylinder, "ReactorVessel", parent, new Vector3(0, 1.8f, 0), new Vector3(2.2f, 1.65f, 2.2f));
            colored.Add(tank.GetComponent<Renderer>());
            Frame(PrimitiveType.Cylinder, "Top", parent, new Vector3(0, 3.45f, 0), new Vector3(1.35f, 0.18f, 1.35f), frame);
            Frame(PrimitiveType.Cylinder, "Mixer", parent, new Vector3(0, 4.1f, 0), new Vector3(0.22f, 0.65f, 0.22f), frame);
        }

        private static void BuildSeparator(Transform parent, Material frame, List<Renderer> colored)
        {
            var vessel = Primitive(PrimitiveType.Cylinder, "SeparatorVessel", parent, new Vector3(0, 1.65f, 0), new Vector3(1.75f, 1.5f, 1.75f));
            colored.Add(vessel.GetComponent<Renderer>());
            Frame(PrimitiveType.Sphere, "Dome", parent, new Vector3(0, 3.15f, 0), new Vector3(1.75f, 0.65f, 1.75f), frame);
            Frame(PrimitiveType.Cube, "Outlet", parent, new Vector3(1.15f, 2.2f, 0), new Vector3(0.7f, 0.22f, 0.22f), frame);
        }

        private static void BuildCompressor(Transform parent, Material frame, List<Renderer> colored)
        {
            var casing = Primitive(PrimitiveType.Sphere, "CompressorCasing", parent, new Vector3(0, 1.65f, 0), new Vector3(2.25f, 2.25f, 1.15f));
            colored.Add(casing.GetComponent<Renderer>());
            Frame(PrimitiveType.Cylinder, "Shaft", parent, new Vector3(0, 1.65f, 0), new Vector3(0.3f, 1.65f, 0.3f), frame, Quaternion.Euler(90, 0, 0));
            Frame(PrimitiveType.Cube, "Motor", parent, new Vector3(0, 1.1f, -1.1f), new Vector3(1.3f, 1.25f, 1.1f), frame);
        }

        private static void BuildStripper(Transform parent, Material frame, List<Renderer> colored)
        {
            var column = Primitive(PrimitiveType.Cylinder, "StripperColumn", parent, new Vector3(0, 2.1f, 0), new Vector3(1.4f, 2.0f, 1.4f));
            colored.Add(column.GetComponent<Renderer>());
            for (var i = 0; i < 4; i++)
                Frame(PrimitiveType.Cylinder, $"TrayRing_{i + 1}", parent, new Vector3(0, 0.8f + i * 0.85f, 0), new Vector3(1.55f, 0.08f, 1.55f), frame);
        }

        private static GameObject CreateProcessLine(params GameObject[] equipmentPrefabs)
        {
            var root = new GameObject("ProcessLine");
            var positions = new[] { -7.5f, -2.5f, 2.5f, 7.5f };
            for (var i = 0; i < equipmentPrefabs.Length; i++)
            {
                var equipment = (GameObject)PrefabUtility.InstantiatePrefab(equipmentPrefabs[i], root.transform);
                equipment.transform.localPosition = new Vector3(positions[i], 0, 0);
                if (i > 0)
                {
                    var pipe = Primitive(PrimitiveType.Cylinder, $"Pipe_{i}", root.transform,
                        new Vector3((positions[i - 1] + positions[i]) / 2f, 1.35f, 0), new Vector3(0.18f, 2.5f, 0.18f));
                    pipe.transform.localRotation = Quaternion.Euler(0, 0, 90);
                    pipe.GetComponent<Renderer>().sharedMaterial = AssetDatabase.LoadAssetAtPath<Material>($"{Materials}/Equipment_Frame.mat");
                }
            }
            var prefab = SavePrefab(root, $"{Prefabs}/ProcessLine.prefab");
            return prefab;
        }

        private static GameObject CreateDashboardPrefab()
        {
            var canvasObject = new GameObject("DashboardCanvas", typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            var canvas = canvasObject.GetComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            var scaler = canvasObject.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920, 1080);

            var panel = UIObject("DashboardPanel", canvasObject.transform, typeof(Image));
            var panelRect = panel.GetComponent<RectTransform>();
            panelRect.anchorMin = new Vector2(0.02f, 0.04f);
            panelRect.anchorMax = new Vector2(0.32f, 0.96f);
            panelRect.offsetMin = panelRect.offsetMax = Vector2.zero;
            panel.GetComponent<Image>().color = new Color(0.025f, 0.045f, 0.075f, 0.94f);

            var title = MakeText(panel.transform, "Title", "TEP DIGITAL TWIN", 34, TextAnchor.MiddleLeft, new Vector2(0.06f, 0.88f), new Vector2(0.94f, 0.97f));
            title.color = new Color(0.62f, 0.85f, 1f);
            var indicator = UIObject("StatusIndicator", panel.transform, typeof(Image)).GetComponent<Image>();
            SetRect(indicator.rectTransform, new Vector2(0.06f, 0.77f), new Vector2(0.13f, 0.84f));
            var status = MakeText(panel.transform, "Status", "NORMAL", 36, TextAnchor.MiddleLeft, new Vector2(0.17f, 0.75f), new Vector2(0.92f, 0.86f));
            var rul = MakeText(panel.transform, "RUL", "RUL  -- h", 42, TextAnchor.MiddleLeft, new Vector2(0.06f, 0.61f), new Vector2(0.94f, 0.73f));
            var trajectory = MakeText(panel.transform, "Trajectory", "Waiting for data", 20, TextAnchor.MiddleLeft, new Vector2(0.06f, 0.54f), new Vector2(0.94f, 0.61f));
            var riskTitle = MakeText(panel.transform, "RiskTitle", "FAILURE RISK", 24, TextAnchor.MiddleLeft, new Vector2(0.06f, 0.43f), new Vector2(0.94f, 0.51f));
            riskTitle.color = new Color(0.62f, 0.85f, 1f);
            var four = MakeText(panel.transform, "Risk4h", "4 HOUR  --", 24, TextAnchor.MiddleLeft, new Vector2(0.06f, 0.33f), new Vector2(0.94f, 0.41f));
            var two = MakeText(panel.transform, "Risk2h", "2 HOUR  --", 24, TextAnchor.MiddleLeft, new Vector2(0.06f, 0.24f), new Vector2(0.94f, 0.32f));
            var one = MakeText(panel.transform, "Risk1h", "1 HOUR  --", 24, TextAnchor.MiddleLeft, new Vector2(0.06f, 0.15f), new Vector2(0.94f, 0.23f));
            var source = MakeText(panel.transform, "Source", "SOURCE  MOCK JSON", 18, TextAnchor.MiddleLeft, new Vector2(0.06f, 0.05f), new Vector2(0.94f, 0.11f));
            source.color = new Color(0.55f, 0.62f, 0.7f);

            var dashboard = panel.AddComponent<DashboardPanel>();
            var serialized = new SerializedObject(dashboard);
            serialized.FindProperty("statusText").objectReferenceValue = status;
            serialized.FindProperty("rulText").objectReferenceValue = rul;
            serialized.FindProperty("trajectoryText").objectReferenceValue = trajectory;
            serialized.FindProperty("fourHourText").objectReferenceValue = four;
            serialized.FindProperty("twoHourText").objectReferenceValue = two;
            serialized.FindProperty("oneHourText").objectReferenceValue = one;
            serialized.FindProperty("statusIndicator").objectReferenceValue = indicator;
            serialized.ApplyModifiedPropertiesWithoutUndo();
            return SavePrefab(canvasObject, $"{Prefabs}/DashboardCanvas.prefab");
        }

        private static GameObject CreateRuntimePrefab()
        {
            var root = new GameObject("DigitalTwinRuntime");
            var source = root.AddComponent<MockPredictionSource>();
            var mock = AssetDatabase.LoadAssetAtPath<TextAsset>($"{Root}/Mock/prediction_sequence.json");
            var sourceSerialized = new SerializedObject(source);
            sourceSerialized.FindProperty("mockSequence").objectReferenceValue = mock;
            sourceSerialized.ApplyModifiedPropertiesWithoutUndo();
            root.AddComponent<DigitalTwinController>();
            return SavePrefab(root, $"{Prefabs}/DigitalTwinRuntime.prefab");
        }

        private static GameObject CreateEnvironmentPrefab()
        {
            var root = new GameObject("Environment");
            var floor = Primitive(PrimitiveType.Cube, "Floor", root.transform, new Vector3(0, -0.25f, 0), new Vector3(22, 0.4f, 9));
            floor.GetComponent<Renderer>().sharedMaterial = CreateMaterial("Floor", new Color(0.055f, 0.075f, 0.1f));
            var camera = new GameObject("Main Camera", typeof(Camera));
            camera.tag = "MainCamera";
            camera.transform.SetParent(root.transform);
            camera.transform.position = new Vector3(2.5f, 8.5f, -18f);
            camera.transform.LookAt(new Vector3(1.5f, 1.7f, 0));
            camera.GetComponent<Camera>().fieldOfView = 52f;
            camera.GetComponent<Camera>().backgroundColor = new Color(0.018f, 0.028f, 0.045f);
            camera.AddComponent<FlyCameraController>();
            var light = new GameObject("Key Light", typeof(Light));
            light.transform.SetParent(root.transform);
            light.transform.rotation = Quaternion.Euler(45, -35, 0);
            light.GetComponent<Light>().type = LightType.Directional;
            light.GetComponent<Light>().intensity = 1.4f;
            return SavePrefab(root, $"{Prefabs}/Environment.prefab");
        }

        private static void CreateDemoScene(GameObject processPrefab, GameObject dashboardPrefab,
            GameObject runtimePrefab, GameObject environmentPrefab)
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var environment = (GameObject)PrefabUtility.InstantiatePrefab(environmentPrefab);
            var process = (GameObject)PrefabUtility.InstantiatePrefab(processPrefab);
            var dashboardObject = (GameObject)PrefabUtility.InstantiatePrefab(dashboardPrefab);
            var runtime = (GameObject)PrefabUtility.InstantiatePrefab(runtimePrefab);
            _ = environment;

            var controller = runtime.GetComponent<DigitalTwinController>();
            var source = runtime.GetComponent<PredictionSource>();
            var dashboard = dashboardObject.GetComponentInChildren<DashboardPanel>();
            var equipment = process.GetComponentsInChildren<EquipmentView>();
            var serialized = new SerializedObject(controller);
            serialized.FindProperty("source").objectReferenceValue = source;
            serialized.FindProperty("dashboard").objectReferenceValue = dashboard;
            var array = serialized.FindProperty("equipment");
            array.arraySize = equipment.Length;
            for (var i = 0; i < equipment.Length; i++) array.GetArrayElementAtIndex(i).objectReferenceValue = equipment[i];
            serialized.ApplyModifiedPropertiesWithoutUndo();

            EditorSceneManager.SaveScene(scene, $"{Scenes}/TEPDigitalTwinDemo.unity");
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene($"{Scenes}/TEPDigitalTwinDemo.unity", true) };
            Selection.activeObject = AssetDatabase.LoadAssetAtPath<SceneAsset>($"{Scenes}/TEPDigitalTwinDemo.unity");
        }

        private static void ValidateGeneratedAssets()
        {
            var variantNames = new[] { "Reactor", "Separator", "Compressor", "Stripper" };
            foreach (var name in variantNames)
            {
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>($"{Prefabs}/{name}.prefab");
                if (prefab == null || PrefabUtility.GetPrefabAssetType(prefab) != PrefabAssetType.Variant)
                    throw new InvalidDataException($"{name} must be a prefab variant.");
            }

            var controller = Object.FindObjectsByType<DigitalTwinController>(
                FindObjectsInactive.Include, FindObjectsSortMode.None).FirstOrDefault();
            if (controller == null) throw new InvalidDataException("Demo scene controller is missing.");
            var serialized = new SerializedObject(controller);
            if (serialized.FindProperty("source").objectReferenceValue == null)
                throw new InvalidDataException("Prediction source is not connected.");
            if (serialized.FindProperty("dashboard").objectReferenceValue == null)
                throw new InvalidDataException("Dashboard is not connected.");
            if (serialized.FindProperty("equipment").arraySize != 4)
                throw new InvalidDataException("Exactly four equipment views are required.");
            if (Object.FindAnyObjectByType<FlyCameraController>() == null)
                throw new InvalidDataException("Fly camera controller is missing.");

            var mock = AssetDatabase.LoadAssetAtPath<TextAsset>($"{Root}/Mock/prediction_sequence.json");
            var sequence = mock == null ? null : JsonUtility.FromJson<PredictionSequence>(mock.text);
            if (sequence?.snapshots == null || sequence.snapshots.Length != 4 ||
                sequence.snapshots.First().Status != ProcessStatus.NORMAL ||
                sequence.snapshots.Last().Status != ProcessStatus.CRITICAL)
                throw new InvalidDataException("Mock sequence must cover NORMAL through CRITICAL.");

            Debug.Log("TEP validation passed: 4 variants, nested process prefab, dashboard and mock sequence.");
        }

        private static GameObject Primitive(PrimitiveType type, string name, Transform parent, Vector3 position, Vector3 scale)
        {
            var item = GameObject.CreatePrimitive(type);
            item.name = name;
            item.transform.SetParent(parent, false);
            item.transform.localPosition = position;
            item.transform.localScale = scale;
            return item;
        }

        private static void Frame(PrimitiveType type, string name, Transform parent, Vector3 position,
            Vector3 scale, Material material, Quaternion rotation = default)
        {
            var item = Primitive(type, name, parent, position, scale);
            item.transform.localRotation = rotation == default ? Quaternion.identity : rotation;
            item.GetComponent<Renderer>().sharedMaterial = material;
        }

        private static GameObject SavePrefab(GameObject root, string path)
        {
            if (AssetDatabase.LoadAssetAtPath<GameObject>(path) != null) AssetDatabase.DeleteAsset(path);
            var prefab = PrefabUtility.SaveAsPrefabAsset(root, path);
            Object.DestroyImmediate(root);
            return prefab;
        }

        private static GameObject UIObject(string name, Transform parent, params System.Type[] components)
        {
            var types = new List<System.Type> { typeof(RectTransform) };
            types.AddRange(components);
            var item = new GameObject(name, types.ToArray());
            item.transform.SetParent(parent, false);
            return item;
        }

        private static Text MakeText(Transform parent, string name, string value, int size,
            TextAnchor anchor, Vector2 min, Vector2 max)
        {
            var item = UIObject(name, parent, typeof(Text));
            var text = item.GetComponent<Text>();
            text.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            text.text = value;
            text.fontSize = size;
            text.alignment = anchor;
            text.color = Color.white;
            text.resizeTextForBestFit = true;
            text.resizeTextMinSize = 12;
            text.resizeTextMaxSize = size;
            SetRect(text.rectTransform, min, max);
            return text;
        }

        private static void SetRect(RectTransform rect, Vector2 min, Vector2 max)
        {
            rect.anchorMin = min;
            rect.anchorMax = max;
            rect.offsetMin = rect.offsetMax = Vector2.zero;
        }
    }
}
#endif
