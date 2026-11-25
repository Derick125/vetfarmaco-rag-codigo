/// Valor de dose: número seguido de unidade de massa/volume/atividade,
/// opcionalmente por kg ou mL (`5 mg/kg`, `0,1 mL`, `2 UI`).
final _dose = RegExp(
  r'\d[\d.,]*\s*(mg|mcg|µg|ug|g|ml|ui|u\.i\.)(\s*/\s*(kg|ml|h|dia))?(?![a-zà-ú])',
  caseSensitive: false,
);

/// `true` se [texto] contém um valor de dose.
///
/// Usado para a regra de segurança do `FRONTEND_SPEC.md` §10: nenhum valor
/// de dose é exibido fora de um parágrafo com `chunkIds` não vazio.
bool contemDose(String texto) => _dose.hasMatch(texto);
