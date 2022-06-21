import PySimpleGUI as sg
import matplotlib
import numpy as np
# ------------------------------- Beginning of GUI CODE -------------------------------

def update(x0, y0, x1, y1):
    """
    Update rectangle information
    """
    # print(repr(x0), repr(y0), repr(x1), repr(y1))
    window['-START-'].update(f'Start: ({x0}, {y0})')
    window['-STOP-'].update(f'Stop: ({x1}, {y1})')
    window['-BOX-'].update(f'Box: ({abs(x1-x0+1)}, {abs(y1-y0+1)})')


# define the window layout
layout = [[sg.Text('Max Projection', key='-TITLE-')],
        [sg.Graph((608, 608), (15, 15), (608, 608), key='-GRAPH-', drag_submits=True, enable_events=True)],
        [sg.Text("Start: None", key="-START-"),sg.Text("Stop: None",  key="-STOP-"), sg.Text("Box: None",   key="-BOX-")],
        [sg.Combo(['Max', 'Min', 'Range', 'Std' ], key='-OPTION-', default_value='Max', readonly=True, auto_size_text=True, enable_events=True)],
        [sg.Button('Submit')]]

# create the form and show it without the plot
window = sg.Window('CropGUI', layout, finalize=True,
                   element_justification='center', font='Helvetica 18')

# add the plot to the window
graph = window['-GRAPH-']
x0, y0 = None, None
x1, y1 = None, None
colors = ['red', 'white']
index = False
box = None
while True:

    event, values = window.read(timeout=100)

    if event == sg.WINDOW_CLOSED:
        break
    elif event in ('-OPTION-'):
        window['-TITLE-'].update(values['-OPTION-'] + " Projection")
        #TODO based on selection it will change the image in -GRAPH-

    elif event in ('-GRAPH-', '-GRAPH-+UP'):
        if (x0, y0) == (None, None):
            x0, y0 = values['-GRAPH-']
        x1, y1 = values['-GRAPH-']
        update(x0, y0, x1, y1)
        if event == '-GRAPH-+UP':
            x0, y0 = None, None

    if box:
        graph.delete_figure(box)
    if None not in (x0, y0, x1, y1):
        box = graph.draw_rectangle((x0, y0), (x1, y1), line_color=colors[index])
        index = not index

window.close()