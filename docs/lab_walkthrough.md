# First-run walkthrough

Use a separate working copy of your project and a short supported recording.
If this is your first installation, complete [Install and open ACE](gui_installation.md)
first. If you do not have a project, [create one from the CSV templates](gui.md#prepare-a-project).
No demonstration recording is bundled; use data you have permission to analyze,
including its original metadata and timestamps.

Choose settings appropriate to the recording and define criteria for accepting
neurons before reviewing them. A default value does not establish that it suits
your acquisition system or calcium indicator. Start small before processing a
complete study.

1. **Open ACE.** Follow [installation and launch](gui_installation.md#5-open-the-gui).
   Check that ACE opens in your browser.
2. **Find your experiment.** Follow [Open ACE and a project](gui.md#open-ace-and-a-project).
   Check its subject, date, and recording folder against your recording information.
3. **Locate the recording.** Follow [Check recording locations](gui.md#check-recording-locations).
   Choose the local recording folder. If the recording is on Box, download it
   outside ACE first; the installed GUI does not download from Box.
4. **Save a note.** Follow [Edit and save](gui.md#edit-and-save-details-or-settings).
   Add a note in **Notes** under **Experiment details**. Save, reload the project,
   and check that the note is still present.
5. **Choose an image area.** Follow [Preview and crop](gui.md#preview-and-crop-a-movie).
   Draw an area of interest, move or resize it, and save. Reload the preview and
   check that it shows your saved selection.
6. **Process the short movie.** Follow [Review and run](gui.md#review-and-run-an-analysis).
   Select **Crop and preprocess movie**, review your settings, input files, and
   output location, and start. Check for a completed run in Results.
7. **Find its outputs.** Follow [Find and reopen results](gui.md#find-and-reopen-results).
   Open the output folder and find the processed movie. Check that it contains
   the intended recording and image area.
8. **Repeat and return.** Repeat the same analysis and check that both runs remain
   available in separate folders. Close the browser tab and reopen it using the
   complete launch address from ACE's terminal. Reopen the project if needed and
   check that both runs remain available. After a server restart, use its new
   launch address.
9. **Extract neurons, if needed.** Follow [Review and run](gui.md#review-and-run-an-analysis)
   with **Calcium imaging (preprocessing and CNMF-E)** and settings suitable for
   your data. Ensure both neuron extraction and estimates saving are enabled.
   Check that the completed run offers **Review extracted neurons**.
10. **Review and export neurons, if needed.** Follow
    [Review neurons](gui.md#review-neurons-and-save-accepted-cells) and apply your
    keep/reject criteria. Make a few decisions, reopen the same estimates to check
    they persist, then finish. Save curated copies and detect events using
    appropriate settings. Check the curation folder for the new outputs.

For electrical or combined recordings, use the [ephys guide](guides/ephys.md)
or [alignment guide](guides/multimodal.md), set the actual channels and
synchronization information, and review both recording inputs where applicable.
A successful movie-preprocessing run does not validate these other workflows.

If a step fails or the instructions are unclear,
[report a problem](gui_installation.md#report-an-installation-problem). Include the
step, computer/operating system, source revision, experiment ID, and screenshots
or exact errors where useful. Remove the private launch token. When evaluating
these instructions, note whether each task was completed independently, needed
help, or could not be completed.

Completing this walkthrough checks the application workflow. Assess the quality
of the scientific results separately before using them in a study.
