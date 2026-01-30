from proof.localctx import LocalContext
from logging import Logger
import sys

def try_hammer(lctx: LocalContext, 
               verified_text: str,
               logger: Logger) -> bool:
    if not lctx.enable_hammer:
        return False

    old_content = lctx.content

    rcontent = lctx.legacy_text
    qlen = len(lctx.legacy_text_cont)
    # First, lets try arithmetical tactics
    rcontent += '\n' + verified_text + '\n first [lia | nia | ring | field | lra | nra]. \n'
    lctx.overwrite(rcontent, is_dup=True)
    _, err = lctx.hammer_dup()
    if err.find('pending proofs') != -1:
        lctx.update_content(rcontent[lctx.legacy_len:])
        return True
    # Second, lets try eauto tactics
    rcontent = lctx.legacy_text + '\n' + verified_text + '\n progress eauto. \n'
    lctx.overwrite(rcontent, is_dup=True)
    _, err = lctx.hammer_dup()
    if err.find('pending proofs') != -1:
        lctx.update_content(rcontent[lctx.legacy_len:])
        return True
    

    rcontent = lctx.legacy_text
    rcontent += '\n' + verified_text + '\n hammer. '
    lctx.overwrite(rcontent, is_dup=True)
    new_tactic, _ = lctx.hammer_dup(True)
    logger.info(f'new_tactic = {new_tactic}')
    hammer_success = False

    if new_tactic is None:
        lctx.update_content(old_content)
    else:
        new_tactic = new_tactic.replace('srun eauto use:', 'srun (eauto) use:')
        rcontent = rcontent.replace(' hammer. ', new_tactic)
        hammer_success = True
        lctx.update_content(rcontent[lctx.legacy_len:])
    
    return hammer_success