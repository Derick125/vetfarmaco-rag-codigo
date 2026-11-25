import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/consulta/domain/formulario_consulta.dart';
import 'package:app/features/consulta/domain/usecases/obter_vocabulario.dart';
import 'package:app/features/consulta/presentation/cubit/consulta_state.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:injectable/injectable.dart';

/// Controla o formulário estruturado de `/consulta`.
@injectable
class ConsultaCubit extends Cubit<ConsultaState> {
  /// Cria o cubit.
  new(this._obterVocabulario, this._montarCorpo) : super(const ConsultaState());

  final ObterVocabulario _obterVocabulario;
  final MontarCorpoConsulta _montarCorpo;

  /// Carrega o vocabulário (servidor ou cópia local).
  Future<void> carregar() async {
    emit(state.copiar(status: StatusVocabulario.carregando));
    final r = await _obterVocabulario();
    r.match(
      (falha) => emit(
        state.copiar(status: StatusVocabulario.falha, mensagem: falha.mensagem),
      ),
      (v) =>
          emit(state.copiar(status: StatusVocabulario.pronto, vocabulario: v)),
    );
  }

  /// Escolhe a espécie; tocar na já escolhida a desmarca.
  void alterarEspecie(String especie) {
    final atual = state.formulario.especie;
    _editar(
      state.formulario.copiar(especie: () => atual == especie ? null : especie),
    );
  }

  /// Atualiza o peso como digitado.
  void alterarPeso(String texto) =>
      _editar(state.formulario.copiar(pesoTexto: texto));

  /// Adiciona um fármaco do vocabulário (ignora repetidos).
  void adicionarFarmaco(String nome) {
    final atuais = state.formulario.farmacos;
    if (atuais.contains(nome)) return;
    _editar(state.formulario.copiar(farmacos: [...atuais, nome]));
  }

  /// Remove um fármaco.
  void removerFarmaco(String nome) => _editar(
    state.formulario.copiar(
      farmacos: [
        for (final f in state.formulario.farmacos)
          if (f != nome) f,
      ],
    ),
  );

  /// Marca ou desmarca uma comorbidade.
  void alternarComorbidade(String chave) {
    final atuais = {...state.formulario.comorbidades};
    if (!atuais.remove(chave)) atuais.add(chave);
    _editar(state.formulario.copiar(comorbidades: atuais));
  }

  /// Atualiza a pergunta como digitada.
  void alterarPergunta(String texto) =>
      _editar(state.formulario.copiar(pergunta: texto));

  void _editar(FormularioConsulta formulario) => emit(
    state.copiar(formulario: formulario, corpo: _montarCorpo(formulario)),
  );
}
