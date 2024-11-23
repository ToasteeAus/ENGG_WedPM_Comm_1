import br_info, tkinter
from tkinter import ttk

class InitPage(tkinter.Frame):
    def __init__(self, parent):
        tkinter.Frame.__init__(self, parent)
        self.parent = parent
        
        self.page_display()
        
    def change_window(self, window_to_change):
        self.app = window_to_change(self.parent)
        self.destroy()

    def page_display(self):
        def on_br_select(event):
            br_selected = br_selector.get()
            br_selected_label.config(text="Selected BR: " + br_selected)

        def on_op_select(event):
            op_selected = op_selector.get()
            op_selected_label.config(text="Selected Mode: " + op_selected)
            
        def on_pressed(self):
            main_window.title("BR: " + br_selector.get() + " - Operation: " + op_selector.get())
            
        
        title = tkinter.Label(main_window, text="Select BladeRunner to control and its operation mode", font=("Segoe UI", 9, 'bold'))
        title.pack(pady=(10, 10))


        selection_frame = tkinter.Frame(main_window)
        selection_frame.pack(pady=5)

        br_selector_title = tkinter.Label(selection_frame, text="BladeRunner: ", anchor="e", width=14).grid(row=0)
        br_selector = ttk.Combobox(selection_frame, values=br_info.brAvail)
        br_selector.grid(row=0, column=1)
        br_selector.set(br_info.brAvail[0])
        br_selector.bind("<<ComboboxSelected>>", on_br_select)

        op_selector_title = tkinter.Label(selection_frame, text="Operation Mode: ", anchor="e", width=14).grid(row=1)
        op_selector = ttk.Combobox(selection_frame, values=br_info.opAvail)
        op_selector.grid(row=1, column=1)
        op_selector.set(br_info.opAvail[0])
        op_selector.bind("<<ComboboxSelected>>", on_op_select)

        br_selected_label = tkinter.Label(main_window, text="Selected BR: " + br_info.brAvail[0]) 
        br_selected_label.pack(pady=(10, 0))

        op_selected_label = tkinter.Label(main_window, text="Selected Mode: " + br_info.opAvail[0]) 
        op_selected_label.pack(pady=(5, 2.5))

        button = tkinter.Button(main_window, text="Startup BladeRunner", width=25, command=on_pressed)
        button.pack()
        
        button = tkinter.Button(main_window, text="Change Window", width=25, command=self.change_window(TempPage))
        button.pack()

if __name__ == "__main__":
    main_window = tkinter.Tk()
    main_window.title("BladeRunner Controller")
    main_window.geometry("400x400")
    main_window.minsize(400, 400)
    
    app = InitPage(main_window)
    
    main_window.mainloop()
