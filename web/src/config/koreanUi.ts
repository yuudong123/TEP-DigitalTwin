const featureLabels: Record<string, string> = {
  'D feed': 'D 원료 공급량', 'E Feed': 'E 원료 공급량', 'A Feed': 'A 원료 공급량', 'A and C Feed': 'A·C 원료 공급량',
  Recycle: '재순환 조절', Purge: '배출 조절', Separator: '분리기 조절', Stripper: '정제기 조절', Steam: '증기 조절',
  'Reactor Coolant': '반응기 냉각수 조절', 'Condenser Coolant': '응축기 냉각수 조절', Agitator: '교반기',
  'msv A Feed': 'A 원료 공급 측정값', 'msv D Feed': 'D 원료 공급 측정값', 'msv E Feed': 'E 원료 공급 측정값', 'msv A and C Feed': 'A·C 원료 공급 측정값',
  'Recycle Flow': '재순환 유량', 'Reactor Feed Rate': '반응기 공급 유량', 'Reactor Pressure': '반응기 압력', 'Reactor Level': '반응기 액위',
  'Reactor Temperature': '반응기 온도', 'Purge Rate': '배출 유량', 'Product Sep Temp': '제품 분리기 온도', 'Product Sep Level': '제품 분리기 액위',
  'Product Sep Pressure': '제품 분리기 압력', 'Product Sep Underflow': '제품 분리기 하부 유량', 'Stripper Level': '정제기 액위', 'Stripper Pressure': '정제기 압력',
  'Stripper Underflow': '정제기 하부 유량', 'Stripper Temp': '정제기 온도', 'Stripper Steam Flow': '정제기 증기 유량', 'Compressor Work': '압축기 동력',
  'Reactor Coolant Temp': '반응기 냉각수 온도', 'Separator Coolant Temp': '분리기 냉각수 온도',
}
export function featureLabel(name: string) {
  if (featureLabels[name]) return featureLabels[name]
  const component = /^Component ([A-H]) to (Reactor|Purge|Product)$/.exec(name)
  if (component) return `${{ Reactor: '반응기 유입', Purge: '배출', Product: '제품' }[component[2]]} ${component[1]} 성분`
  return '기타 공정 변수'
}
export function trajectoryLabel(key: string) {
  const match = /^case(\d+)::(\d+)$/.exec(key)
  return match ? `시나리오 ${match[1]} · 실행 ${match[2]}` : '재생 데이터'
}
export function transformLabel(transform: string) {
  return ({ current: '현재값', mean: '평균', max: '최댓값', min: '최솟값', std: '표준편차', slope: '변화 기울기', delta: '변화량' } as Record<string, string>)[transform] ?? '시계열 특성'
}
