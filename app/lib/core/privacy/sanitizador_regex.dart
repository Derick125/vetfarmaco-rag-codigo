import 'package:app/features/consulta/domain/sanitizador.dart';
import 'package:injectable/injectable.dart';

/// [Sanitizador] por expressões regulares (`docs/FRONTEND_SPEC.md` §9).
///
/// Diverge do §9 num ponto: `paciente`/`animal`/`nome` só mascaram quando
/// seguidos de dois-pontos: sem isso, "neste paciente?" viraria "paciente: ..."
/// e destruiria perguntas clínicas legítimas.
@LazySingleton(as: Sanitizador)
class SanitizadorRegex implements Sanitizador {
  /// Cria o sanitizador.
  const new();

  static final _cpf = RegExp(r'(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)');
  static final _telefone = RegExp(
    r'(?<![\d])\(?\d{2}\)?\s?9?\d{4}-?\d{4}(?!\d)',
  );
  static final _tutor = RegExp(
    r'\b(tutor|tutora|propriet[áa]rio|respons[áa]vel)\s*:?\s*[^\n,;.]+',
    caseSensitive: false,
  );
  static final _animal = RegExp(
    r'\b(paciente|animal|nome)\s*:\s*[^\n,;.]+',
    caseSensitive: false,
  );
  static final _prontuario = RegExp(
    r'\b(prontu[áa]rio|registro|ficha)\s*n?[ºo°]?\s*[\w-]+',
    caseSensitive: false,
  );

  @override
  String sanitizar(String entrada) => entrada
      .replaceAll(_cpf, '[CPF]')
      .replaceAll(_telefone, '[TELEFONE]')
      .replaceAllMapped(_tutor, (m) => '${m[1]}: [REMOVIDO]')
      .replaceAllMapped(_animal, (m) => '${m[1]}: [REMOVIDO]')
      .replaceAllMapped(_prontuario, (m) => '${m[1]}: [REMOVIDO]');
}
