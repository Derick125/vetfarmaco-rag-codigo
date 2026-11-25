import 'package:app/core/error/failures.dart';
import 'package:fpdart/fpdart.dart';

/// Persistência da introdução de primeiro uso (`docs/FRONTEND_SPEC.md` §21).
abstract interface class OnboardingRepository {
  /// `true` se a introdução já foi vista (ou pulada) neste dispositivo.
  Future<Either<Failure, bool>> introducaoVista();

  /// Marca a introdução como vista.
  Future<Either<Failure, Unit>> marcarIntroducaoVista();
}
