import caiman as cm

# Functions that don't apply to a single experiment
def find_same_neurons(session_list, FOV_dims, template_list = None, background=None, plot_results=False):
    """Track ROIs across multiple imaging sessions.
    
    Args:
        session_list: Numpy array of spatial footprints (estimates.A) from each session.
        template_list: Numpy array of one frame from each session's movie.
        FOV_dims: Dimensions of the field of view as a tuple.
        background: Background image for plotting (only used with 2 sessions).
        plot_results: If True and 2 sessions, plot the results.
        
    Returns:
        If 2 sessions: (matched_ROIs1, matched_ROIs2, non_matched1, non_matched2, performance, A2).
        If >2 sessions: (A_union, assignments, matchings).
    """
    print('Finding common neurons between recordings...')
    if session_list.size > 2:
        return cm.base.rois.register_multisession(session_list, FOV_dims, templates=template_list)
    else:
        if template_list is not None:
            return cm.base.rois.register_ROIs(session_list[0], session_list[1], FOV_dims, template1=template_list[0], template2=template_list[1], Cn=background, plot_results=plot_results)
        else:
            return cm.base.rois.register_ROIs(session_list[0], session_list[1], FOV_dims, Cn=background, plot_results=plot_results)