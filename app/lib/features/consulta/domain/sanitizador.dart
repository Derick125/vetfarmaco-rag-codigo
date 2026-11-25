/// Mascara PII na pergunta, antes de qualquer envio (`CLAUDE.md` §4.3).
///
/// Varredura best-effort sobre texto livre: não substitui a estruturação dos
/// campos, que já impede nome de tutor/animal de entrar na carga.
abstract interface class Sanitizador {
  /// Devolve [entrada] com CPF, telefone, tutor, paciente e prontuário
  /// mascarados.
  String sanitizar(String entrada);
}
