import 'package:app/features/historico/domain/resposta_salva.dart';
import 'package:equatable/equatable.dart';

/// Situação de `/historico` (`docs/FRONTEND_SPEC.md` §12).
enum StatusHistorico {
  /// Lendo o `hive_ce`.
  carregando,

  /// Há respostas guardadas.
  comItens,

  /// Nenhuma resposta guardada.
  vazio,

  /// Falha ao ler; veja `HistoricoState.mensagem`.
  falha,
}

/// Estado do histórico.
class HistoricoState extends Equatable {
  /// Cria o estado.
  const new({
    this.status = StatusHistorico.carregando,
    this.itens = const [],
    this.offline = false,
    this.mensagem,
  });

  /// Situação.
  final StatusHistorico status;

  /// Respostas, da mais recente para a mais antiga.
  final List<RespostaSalva> itens;

  /// Sem rede: a faixa avisa que só há respostas salvas.
  final bool offline;

  /// Mensagem de falha.
  final String? mensagem;

  @override
  List<Object?> get props => [status, itens, offline, mensagem];
}
