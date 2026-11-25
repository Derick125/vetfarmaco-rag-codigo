import 'package:app/features/ajustes/domain/usecases/obter_condicao_campanha.dart';
import 'package:app/features/ajustes/domain/usecases/obter_endereco_backend.dart';
import 'package:app/features/ajustes/domain/usecases/salvar_condicao_campanha.dart';
import 'package:app/features/ajustes/domain/usecases/salvar_endereco_backend.dart';
import 'package:app/features/ajustes/domain/usecases/testar_backend.dart';
import 'package:app/features/ajustes/presentation/cubit/ajustes_state.dart';
import 'package:app/features/telemetria/domain/condicao_campanha.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:injectable/injectable.dart';

/// Controla `/ajustes`: endereço do back-end, teste e gravação.
@injectable
class AjustesCubit extends Cubit<AjustesState> {
  /// Cria o cubit.
  new(
    this._obter,
    this._testar,
    this._salvar,
    this._obterCondicao,
    this._salvarCondicao,
  ) : super(const AjustesState());

  final ObterEnderecoBackend _obter;
  final TestarBackend _testar;
  final SalvarEnderecoBackend _salvar;
  final ObterCondicaoCampanha _obterCondicao;
  final SalvarCondicaoCampanha _salvarCondicao;

  /// Lê o endereço em vigor (ajuste salvo ou `--dart-define`).
  Future<void> carregar() async {
    final endereco = await _obter();
    emit(
      AjustesState(endereco: endereco ?? '', condicao: await _obterCondicao()),
    );
  }

  /// Chama `/health` no endereço digitado.
  Future<void> testar(String entrada) async {
    emit(state.copiar(status: StatusTeste.testando, salvo: false));
    final r = await _testar(entrada);
    r.match(
      (falha) => emit(
        state.copiar(status: StatusTeste.falha, mensagem: falha.mensagem),
      ),
      (_) => emit(state.copiar(status: StatusTeste.ok)),
    );
  }

  /// Grava o endereço digitado.
  Future<void> salvar(String entrada) async {
    final r = await _salvar(entrada);
    r.match(
      (falha) => emit(
        state.copiar(status: StatusTeste.falha, mensagem: falha.mensagem),
      ),
      (endereco) => emit(state.copiar(endereco: endereco, salvo: true)),
    );
  }

  /// Escolhe a condição de rede da campanha e a grava na hora; escolher a
  /// que já está marcada a desmarca (`naoInformada`).
  Future<void> alterarCondicao(CondicaoCampanha condicao) async {
    final nova = state.condicao == condicao
        ? CondicaoCampanha.naoInformada
        : condicao;
    final r = await _salvarCondicao(nova);
    r.match(
      (falha) => emit(
        state.copiar(status: StatusTeste.falha, mensagem: falha.mensagem),
      ),
      (_) => emit(state.copiar(condicao: nova)),
    );
  }
}
