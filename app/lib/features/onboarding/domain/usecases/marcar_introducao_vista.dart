import 'package:app/core/error/failures.dart';
import 'package:app/features/onboarding/domain/repositories/onboarding_repository.dart';
import 'package:fpdart/fpdart.dart';

/// Marca a introdução de primeiro uso como vista (concluída ou pulada).
class MarcarIntroducaoVista {
  /// Cria o caso de uso.
  const new(this._repositorio);

  final OnboardingRepository _repositorio;

  /// Grava a marca; a introdução não volta a ser mostrada.
  Future<Either<Failure, Unit>> call() => _repositorio.marcarIntroducaoVista();
}
