/// Acesso à configuração local necessária para decidir o destino inicial do
/// app (`BootstrapCubit`, `docs/FRONTEND_SPEC.md` §7).
abstract interface class ConfiguracaoRepository {
  /// Endereço do back-end configurado em `/ajustes`. `null` ou vazio quando
  /// ainda não foi definido.
  Future<String?> enderecoBackend();

  /// Data/hora do aceite do termo de uso clínico (`/termo`), ou `null`
  /// quando o termo ainda não foi aceito neste dispositivo.
  Future<DateTime?> termoAceitoEm();
}
