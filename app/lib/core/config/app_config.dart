/// Configuração de build, injetada por `--dart-define`.
///
/// Nenhuma chave do Gemini ou do Supabase existe no app (`CLAUDE.md` §4.4):
/// só o endereço padrão do back-end e a chave do cliente (`X-API-Key`).
class AppConfig {
  /// Cria a configuração com valores explícitos (testes).
  const new({this.apiBaseUrl = '', this.clientApiKey = ''});

  /// Lê `API_BASE_URL` e `CLIENT_API_KEY` do `--dart-define`.
  const new fromEnvironment()
    : apiBaseUrl = const String.fromEnvironment('API_BASE_URL'),
      clientApiKey = const String.fromEnvironment('CLIENT_API_KEY');

  /// Endereço padrão do back-end; pode ser sobreposto em `/ajustes`.
  final String apiBaseUrl;

  /// Valor enviado no cabeçalho `X-API-Key`.
  final String clientApiKey;
}
