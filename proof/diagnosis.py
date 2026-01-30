from coqpyt.coq.proof_file import ProofFile
from enum import Enum
from logging import getLogger

logger = getLogger('Diagnosis')


from proof.util import (
    get_err_msg,
    get_goal_cfg, 
    is_end_proof,
    no_goal,
)


class ErrType(Enum):
    VALID = 0,
    REDUNDANT = 1,
    TACTIC_FAILED = 2,
    OTHER = 100

    def __repr__(self) -> str:
        return f'(ErrorType: {self.name})'

    def __str__(self) -> str:
        return f'(ErrorType: {self.name})'


class ErrInfo:
    def __init__(self, err_type: ErrType, path: str, steps_taken: int):
        self.type = err_type
        self.path = path
        self.steps_taken = steps_taken
    
    def __repr__(self) -> str:
        return f'(ErrInfo: {str(self.type)}, {self.path}, {self.steps_taken})'


def diagnosis(main_path: str, workspace, disk_cache: bool = True) -> ErrInfo:
    '''
    @Param main_path: str, the coq file to be diagnosised
    @Param disk_cache: bool, whether to use disk cache
    @Return ErrInfo object:
            type: ErrType, the type of error
            path: str, the path of the proof file
            steps_taken: int, the number of steps taken
    '''
    logger.info('workspace = %s', workspace)
    logger.info('main_path = %s', main_path)
    with ProofFile(main_path, workspace=workspace, 
                   use_disk_cache=disk_cache,
                   timeout=150) as pfile:
        ty = ErrType.VALID
        
        for step in pfile.steps:
            is_valid, msg = get_err_msg(step)
            goal_cfg = get_goal_cfg(pfile.current_goals)
            if not is_valid:
                ty = (ErrType.REDUNDANT 
                      if no_goal(goal_cfg) else ErrType.TACTIC_FAILED)
            if ty != ErrType.VALID:
                logger.log(15, 'TextMsg = %s', step.text + '\n' + msg)
                return ErrInfo(ty, main_path, pfile.steps_taken)
            pfile.exec(1)

        if not no_goal(goal_cfg):
            ty = ErrType.TACTIC_FAILED

        return ErrInfo(ty, main_path, pfile.steps_taken)