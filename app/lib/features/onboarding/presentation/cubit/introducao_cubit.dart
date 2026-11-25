import 'package:app/features/onboarding/domain/usecases/consultar_introducao_vista.dart';
import 'package:app/features/onboarding/domain/usecases/marcar_introducao_vista.dart';
import 'package:app/features/onboarding/presentation/cubit/introducao_state.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

/// Controla a introdução de primeiro uso (`docs/FRONTEND_SPEC.md` §21).
///
/// Fora do fluxo de consulta medido: não toca em telemetria.
class IntroducaoCubit extends Cubit<IntroducaoState> {
  /// Cria o cubit.
  new(this._consultar, this._marcar) : super(const IntroducaoCarregando());

  final ConsultarIntroducaoVista _consultar;
  final MarcarIntroducaoVista _marcar;

  /// Lê a marca persistida; sem ela, mostra os cartões.
  ///
  /// Falha de leitura mostra a introdução: no máximo ela aparece de novo.
  Future<void> carregar() async {
    final r = await _consultar();
    final vista = r.getOrElse((_) => false);
    emit(vista ? const IntroducaoJaVista() : const IntroducaoExibindo());
  }

  /// Conclui ou pula: grava a marca e segue para a consulta.
  ///
  /// Falha de gravação não trava o usuário: a introdução só reaparece.
  Future<void> concluir() async {
    await _marcar();
    emit(const IntroducaoConcluida());
  }
}
