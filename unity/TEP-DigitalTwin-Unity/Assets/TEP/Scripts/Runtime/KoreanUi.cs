using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace TEP.DigitalTwin
{
    public static class KoreanUi
    {
        private static readonly Dictionary<string, string> Features = new Dictionary<string, string>
        {
            { "D feed", "D 원료 공급량" }, { "E Feed", "E 원료 공급량" },
            { "A Feed", "A 원료 공급량" }, { "A and C Feed", "A·C 원료 공급량" },
            { "Recycle", "재순환 조절" }, { "Purge", "배출 조절" },
            { "Separator", "분리기 조절" }, { "Stripper", "정제기 조절" },
            { "Steam", "증기 조절" }, { "Reactor Coolant", "반응기 냉각수 조절" },
            { "Condenser Coolant", "응축기 냉각수 조절" }, { "Agitator", "교반기" },
            { "msv A Feed", "A 원료 공급 측정값" }, { "msv D Feed", "D 원료 공급 측정값" },
            { "msv E Feed", "E 원료 공급 측정값" }, { "msv A and C Feed", "A·C 원료 공급 측정값" },
            { "Recycle Flow", "재순환 유량" }, { "Reactor Feed Rate", "반응기 공급 유량" },
            { "Reactor Pressure", "반응기 압력" }, { "Reactor Level", "반응기 액위" },
            { "Reactor Temperature", "반응기 온도" }, { "Purge Rate", "배출 유량" },
            { "Product Sep Temp", "제품 분리기 온도" }, { "Product Sep Level", "제품 분리기 액위" },
            { "Product Sep Pressure", "제품 분리기 압력" }, { "Product Sep Underflow", "제품 분리기 하부 유량" },
            { "Stripper Level", "정제기 액위" }, { "Stripper Pressure", "정제기 압력" },
            { "Stripper Underflow", "정제기 하부 유량" }, { "Stripper Temp", "정제기 온도" },
            { "Stripper Steam Flow", "정제기 증기 유량" }, { "Compressor Work", "압축기 동력" },
            { "Reactor Coolant Temp", "반응기 냉각수 온도" }, { "Separator Coolant Temp", "분리기 냉각수 온도" },
            { "Liquid Input Stripper", "정제기 액체 유입" }, { "Liquid Input Separator", "분리기 액체 유입" },
            { "Liquid Input Reactor", "반응기 액체 유입" },
        };

        public static string Status(ProcessStatus status) => status switch
        {
            ProcessStatus.CRITICAL => "위험",
            ProcessStatus.WARNING => "경고",
            ProcessStatus.CAUTION => "주의",
            _ => "정상",
        };

        public static string Equipment(string name) => name switch
        {
            "Reactor" => "반응기", "Separator" => "분리기", "Compressor" => "압축기",
            "Stripper" => "정제기", _ => "설비",
        };

        public static string Feature(string name)
        {
            if (name == null) return "변수 정보 없음";
            var source = name.Split(new[] { "__" }, System.StringSplitOptions.None)[0];
            if (Features.TryGetValue(source, out var label)) return label;
            var component = Regex.Match(source, @"^Component ([A-H]) to (Reactor|Purge|Product)$");
            if (component.Success)
            {
                var destination = component.Groups[2].Value switch { "Reactor" => "반응기 유입", "Purge" => "배출", _ => "제품" };
                return destination + " " + component.Groups[1].Value + " 성분";
            }
            return "기타 공정 변수";
        }

        public static string Transform(RiskFactor factor)
        {
            var label = factor.transform switch
            {
                "current" => "현재값", "mean" => "평균", "max" => "최댓값", "min" => "최솟값",
                "std" => "표준편차", "slope" => "변화 기울기", "delta" => "변화량", _ => "시계열 특성",
            };
            var window = Regex.Match(factor.feature ?? "", @"_(\d+)m$");
            return window.Success ? "최근 " + window.Groups[1].Value + "분 " + label : label;
        }

        public static string Trajectory(string key)
        {
            var match = Regex.Match(key ?? "", @"^case(\d+)::(\d+)$");
            return match.Success ? "시나리오 " + match.Groups[1].Value + " · 실행 " + match.Groups[2].Value : "재생 데이터";
        }
    }
}
