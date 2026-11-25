import 'package:app/features/historico/domain/usecases/listar_historico.dart';
import 'package:app/features/historico/domain/usecases/remover_resposta_salva.dart';
import 'package:app/features/historico/presentation/cubit/historico_state.dart';
import 'package:app/features/telemetria/domain/repositories/telemetria_repository.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:injectable/injectable.dart';

/// Controla `/historico`: lista, remoção e a faixa offline.
@injectable
class HistoricoCubit extends Cubit<HistoricoState> {
  /// Cria o cubit.
  new(this._listar, this._remover, this._rede) : super(const HistoricoState());

  final ListarHistorico _listar;
  final RemoverRespostaSalva _remover;
  final CondicaoRede _rede;

  /// Lê as respostas guardadas e a condição de rede.
  Future<void> carregar() async {
    emit(const HistoricoState());
    final offline = (await _rede.atual()) == 'none';
    final r = await _listar();
    if (isClosed) return;
    r.match(
      (f) => emit(
        HistoricoState(
          status: StatusHistorico.falha,
          offline: offline,
          mensagem: f.mensagem,
        ),
      ),
      (lista) => emit(
        HistoricoState(
          status: lista.isEmpty
              ? StatusHistorico.vazio
              : StatusHistorico.comItens,
          itens: lista,
          offline: offline,
        ),
      ),
    );
  }

  /// Remove a resposta de [chave] e atualiza a lista.
  Future<void> remover(String chave) async {
    final r = await _remover(chave);
    if (isClosed) return;
    r.match(
      (f) => emit(
        HistoricoState(
          status: StatusHistorico.falha,
          itens: state.itens,
          offline: state.offline,
          mensagem: f.mensagem,
        ),
      ),
      (_) {
        final restantes = [
          for (final i in state.itens)
            if (i.chave != chave) i,
        ];
        emit(
          HistoricoState(
            status: restantes.isEmpty
                ? StatusHistorico.vazio
                : StatusHistorico.comItens,
            itens: restantes,
            offline: state.offline,
          ),
        );
      },
    );
  }
}
