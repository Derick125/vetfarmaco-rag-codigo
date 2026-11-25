import 'package:app/features/termo/domain/usecases/aceitar_termo.dart';
import 'package:app/features/termo/domain/usecases/consultar_aceite_termo.dart';
import 'package:app/features/termo/presentation/cubit/termo_state.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:injectable/injectable.dart';

/// Controla o aceite do termo de uso (`docs/FRONTEND_SPEC.md` §8).
@injectable
class TermoCubit extends Cubit<TermoState> {
  /// Cria o cubit.
  new(this._consultar, this._aceitar) : super(const NaoAceito());

  final ConsultarAceiteTermo _consultar;
  final AceitarTermo _aceitar;

  /// Lê o aceite persistido.
  Future<void> carregar() async {
    final r = await _consultar();
    r.match(
      (falha) => emit(NaoAceito(falha: falha)),
      (quando) => emit(quando == null ? const NaoAceito() : Aceito(quando)),
    );
  }

  /// Grava o aceite.
  Future<void> aceitar() async {
    final r = await _aceitar();
    r.match((falha) => emit(NaoAceito(falha: falha)), (q) => emit(Aceito(q)));
  }
}
