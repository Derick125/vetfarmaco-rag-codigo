/// Condição de rede da campanha de telemetria, escolhida à mão em Ajustes.
///
/// O `connectivity_plus` distingue Wi-Fi de rede móvel, mas não 4G de 5G; a
/// condição vem do pesquisador e é gravada em cada registro.
enum CondicaoCampanha {
  /// Nada escolhido.
  naoInformada('nao_informada', 'Não informada'),

  /// Wi-Fi.
  wifi('wifi', 'Wi-Fi'),

  /// Rede móvel 4G.
  g4('4g', '4G'),

  /// Rede móvel 5G.
  g5('5g', '5G');

  new(this.rotulo, this.titulo);

  /// Valor gravado no CSV.
  final String rotulo;

  /// Texto exibido ao usuário.
  final String titulo;

  /// Condição de [nome] (o `name` do enum); `naoInformada` se desconhecido.
  static CondicaoCampanha dePorNome(String? nome) => values.firstWhere(
    (c) => c.name == nome,
    orElse: () => CondicaoCampanha.naoInformada,
  );
}
