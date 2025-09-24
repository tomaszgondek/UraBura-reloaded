import re
import csv
import os
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import random

DATA_FILE = "data.csv"

# --- Device recognition rules ---
def recognize_device_type(code: str) -> str:
    s = code.strip()
    if not s:
        return "Nieznany"

    if re.fullmatch(r'\d{20,}', s):
        return "Terminal płatniczy"

    if re.fullmatch(r'\d{2}[A-Z]\d{7,}', s):
        return "Komputer kasowy"

    if re.fullmatch(r'[A-Z]{2}\d{9,}', s, flags=re.IGNORECASE):
        return "Drukarka fiskalna N/S"

    if re.fullmatch(r'[A-Z]{3}\d{10,}', s, flags=re.IGNORECASE):
        return "Drukarka fiskalna N/U"

    if re.fullmatch(r'[A-Z]{1}\d{2,}[A-Z]{1}\d{5,}', s):
        return "Skaner"

    if re.fullmatch(r'\(01\)\d{13}\(21\)EMPOS\d{5,}', s):
        return "Tacka RFID"

    if re.fullmatch(r'\(01\)\d{13}\(21\)EMPOSQCO\d{6,}', s):
        return "Kosz"

    return "Nieznany"


class InventoryApp:
    def __init__(self, root):
        self.root = root
        root.title("Inwentaryzacja - skanery kodów")
        root.geometry("1000x600")

        # --- Top panel ---
        frm_top = ttk.Frame(root, padding=8)
        frm_top.pack(fill=tk.X)

        # Shop entry
        ttk.Label(frm_top, text="Sklep:").pack(side=tk.LEFT, padx=(0, 6))
        self.shop_var = tk.StringVar()
        self.shop_entry = ttk.Entry(frm_top, textvariable=self.shop_var, width=6)
        self.shop_entry.pack(side=tk.LEFT, padx=(0, 12))
        self.shop_entry.bind("<Return>", self.add_shop)

        self.shop_combo_var = tk.StringVar()
        self.shop_combo = ttk.Combobox(frm_top, textvariable=self.shop_combo_var, state="readonly", width=10)
        self.shop_combo.pack(side=tk.LEFT, padx=(0, 12))
        self.shop_combo.bind("<<ComboboxSelected>>", self.switch_shop)

        # Cash register entry
        ttk.Label(frm_top, text="Kasa:").pack(side=tk.LEFT, padx=(0, 6))
        self.cash_register_var = tk.StringVar()
        self.cash_register_entry = ttk.Entry(frm_top, textvariable=self.cash_register_var, width=6)
        self.cash_register_entry.pack(side=tk.LEFT, padx=(0, 12))
        self.cash_register_entry.bind("<Return>", self.add_cash_register)

        self.cash_register_combo_var = tk.StringVar()
        self.cash_register_combo = ttk.Combobox(frm_top, textvariable=self.cash_register_combo_var, state="readonly", width=10)
        self.cash_register_combo.pack(side=tk.LEFT, padx=(0, 12))
        self.cash_register_combo.bind("<<ComboboxSelected>>", self.switch_cash_register)

        # Code entry
        ttk.Label(frm_top, text="Kod (numer seryjny):").pack(side=tk.LEFT)
        self.code_var = tk.StringVar()
        self.code_entry = ttk.Entry(frm_top, textvariable=self.code_var, width=40)
        self.code_entry.pack(side=tk.LEFT, padx=(6, 6))
        self.code_entry.bind("<Return>", self.on_submit)
        self.code_entry.focus_set()

        # Dropdown menu
        self.menu_button = ttk.Menubutton(frm_top, text="Więcej funkcji")
        self.menu = tk.Menu(self.menu_button, tearoff=0)
        self.menu.add_command(label="Usuń sklep", command=self.remove_shop)
        self.menu.add_command(label="Usuń kasę", command=self.remove_cash_register)
        self.menu.add_separator()
        self.menu.add_command(label="Usuń zaznaczone", command=self.remove_selected)
        self.menu.add_command(label="Wyczyść listę", command=self.clear_all)
        self.menu.add_separator()
        self.menu.add_command(label="Policz ilość neuronów", command=self.neuron_count)
        self.menu.add_separator()
        self.menu.add_command(label="Wyjdź", command=self.root.quit)
        self.menu_button["menu"] = self.menu
        self.menu_button.pack(side=tk.RIGHT, padx=(6, 0))

        # --- Treeview ---
        cols = ("idx", "code", "type", "notes")
        self.tree = ttk.Treeview(root, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("idx", text="#")
        self.tree.heading("code", text="Kod / S/N")
        self.tree.heading("type", text="Typ urządzenia")
        self.tree.heading("notes", text="Uwagi")
        self.tree.column("idx", width=40, anchor="center")
        self.tree.column("code", width=300, anchor="w")
        self.tree.column("type", width=180, anchor="center")
        self.tree.column("notes", width=200, anchor="w")

        self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.tree.bind("<Double-1>", self.on_double_click)

        # --- Status ---
        frm_status = ttk.Frame(root, padding=6)
        frm_status.pack(fill=tk.X)
        self.status_var = tk.StringVar(value="Pozycje: 0")
        ttk.Label(frm_status, textvariable=self.status_var).pack(side=tk.LEFT)

        # --- Data store ---
        self.rows = []
        self.shops = []
        self.cash_registers = {}
        self.current_shop = None
        self.current_cash_register = None

        self.device_types = [
            "Nieznany",
            "Terminal płatniczy",
            "Komputer kasowy",
            "Drukarka fiskalna N/S",
            "Drukarka fiskalna N/U",
            "Skaner",
            "Tacka RFID",
            "Kosz"
        ]

        # Load data from CSV
        self.load_data()
        self.update_shop_combo()
        self.update_cash_register_combo()
        self.update_treeview()

    # --- CSV handling ---
    def load_data(self):
        self.rows.clear()
        if not os.path.exists(DATA_FILE):
            return
        with open(DATA_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.rows.append(row)
        # rebuild shops and registers
        self.shops = sorted(list({r["shop"] for r in self.rows}))
        self.cash_registers = {s: sorted({r["cash_register"] for r in self.rows if r["shop"] == s}) for s in self.shops}
        if self.shops:
            self.current_shop = self.shops[0]
        if self.current_shop and self.cash_registers[self.current_shop]:
            self.current_cash_register = self.cash_registers[self.current_shop][0]

    def save_data(self):
        with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["shop", "cash_register", "code", "type", "time", "notes"])
            writer.writeheader()
            for row in self.rows:
                writer.writerow(row)

    # --- Shop handling ---
    def add_shop(self, event=None):
        shop = self.shop_var.get().strip()
        if not shop:
            return
        if shop not in self.shops:
            self.shops.append(shop)
            self.shops.sort(key=lambda x: int(x) if x.isdigit() else x)
            self.cash_registers[shop] = []
        self.current_shop = shop
        self.shop_var.set("")
        self.update_shop_combo()
        self.update_cash_register_combo()
        self.update_treeview()

    def switch_shop(self, event=None):
        shop = self.shop_combo_var.get()
        if not shop:
            return
        self.current_shop = shop
        self.update_cash_register_combo()
        self.update_treeview()

    def remove_shop(self):
        if not self.current_shop:
            return
        if messagebox.askyesno("Usuń sklep", f"Czy na pewno usunąć sklep {self.current_shop}?"):
            self.shops.remove(self.current_shop)
            self.cash_registers.pop(self.current_shop, None)
            self.rows = [r for r in self.rows if r["shop"] != self.current_shop]
            self.save_data()
            self.current_shop = self.shops[0] if self.shops else None
            self.update_shop_combo()
            self.update_cash_register_combo()
            self.update_treeview()

    def update_shop_combo(self):
        self.shop_combo["values"] = self.shops
        if self.current_shop:
            self.shop_combo_var.set(self.current_shop)
        else:
            self.shop_combo_var.set("")

    # --- Cash register handling ---
    def add_cash_register(self, event=None):
        if not self.current_shop:
            messagebox.showwarning("Brak sklepu", "Najpierw dodaj sklep.")
            return
        cash_register = self.cash_register_var.get().strip()
        if not cash_register:
            return
        if cash_register not in self.cash_registers[self.current_shop]:
            self.cash_registers[self.current_shop].append(cash_register)
            self.cash_registers[self.current_shop].sort(key=lambda x: int(x) if x.isdigit() else x)
        self.current_cash_register = cash_register
        self.cash_register_var.set("")
        self.update_cash_register_combo()
        self.update_treeview()

    def switch_cash_register(self, event=None):
        cash_register = self.cash_register_combo_var.get()
        if not cash_register:
            return
        self.current_cash_register = cash_register
        self.update_treeview()

    def remove_cash_register(self):
        if not (self.current_shop and self.current_cash_register):
            return
        if messagebox.askyesno("Usuń kasę", f"Czy na pewno usunąć kasę {self.current_cash_register}?"):
            registers = self.cash_registers.get(self.current_shop, [])
            if self.current_cash_register in registers:
                registers.remove(self.current_cash_register)
            self.rows = [r for r in self.rows if not (r["shop"] == self.current_shop and r["cash_register"] == self.current_cash_register)]
            self.save_data()
            self.current_cash_register = registers[0] if registers else None
            self.update_cash_register_combo()
            self.update_treeview()

    def update_cash_register_combo(self):
        if not self.current_shop:
            self.cash_register_combo["values"] = []
            self.cash_register_combo_var.set("")
            return
        registers = self.cash_registers.get(self.current_shop, [])
        self.cash_register_combo["values"] = registers
        if self.current_cash_register in registers:
            self.cash_register_combo_var.set(self.current_cash_register)
        elif registers:
            self.current_cash_register = registers[0]
            self.cash_register_combo_var.set(self.current_cash_register)
        else:
            self.current_cash_register = None
            self.cash_register_combo_var.set("")

    # --- Add entry ---
    def on_submit(self, event=None):
        if not (self.current_shop and self.current_cash_register):
            messagebox.showwarning("Brak sklepu/kasy", "Najpierw dodaj sklep i kasę.")
            return
        code = self.code_var.get().strip()
        if not code:
            return
        dev_type = recognize_device_type(code)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.rows.append({
            "shop": self.current_shop,
            "cash_register": self.current_cash_register,
            "code": code,
            "type": dev_type,
            "time": timestamp,
            "notes": ""
        })
        self.save_data()
        self.update_treeview()
        self.code_var.set("")
        self.code_entry.focus_set()

    # --- Treeview editing ---
    def on_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item_id:
            return
        x, y, width, height = self.tree.bbox(item_id, column)
        col = self.tree["columns"].index(column.strip("#"))  # idx=0->idx,1->code,...
        values = self.tree.item(item_id, "values")
        idx = int(values[0]) - 1
        current_rows = [r for r in self.rows if r["shop"] == self.current_shop and r["cash_register"] == self.current_cash_register]
        if idx >= len(current_rows):
            return
        row = current_rows[idx]

        if column == "#2":  # code
            value = row["code"]
            entry = ttk.Entry(self.tree)
            entry.place(x=x, y=y, width=width, height=height)
            entry.insert(0, value)
            entry.focus_set()

            def save_edit(event=None):
                new_val = entry.get().strip()
                row["code"] = new_val
                row["type"] = recognize_device_type(new_val)
                self.save_data()
                self.update_treeview()
                entry.destroy()

            entry.bind("<Return>", save_edit)
            entry.bind("<FocusOut>", lambda e: entry.destroy())

        elif column == "#3":  # type
            current_val = row["type"]
            combo = ttk.Combobox(self.tree, values=self.device_types, state="readonly")
            combo.place(x=x, y=y, width=width, height=height)
            combo.set(current_val)
            combo.focus_set()

            def save_combo(event=None):
                row["type"] = combo.get()
                self.save_data()
                self.update_treeview()
                combo.destroy()

            combo.bind("<<ComboboxSelected>>", save_combo)
            combo.bind("<FocusOut>", lambda e: combo.destroy())

        elif column == "#5":  # notes
            value = row["notes"]
            entry = ttk.Entry(self.tree)
            entry.place(x=x, y=y, width=width, height=height)
            entry.insert(0, value)
            entry.focus_set()

            def save_notes(event=None):
                row["notes"] = entry.get().strip()
                self.save_data()
                self.update_treeview()
                entry.destroy()

            entry.bind("<Return>", save_notes)
            entry.bind("<FocusOut>", lambda e: entry.destroy())

    # --- Treeview management ---
    def update_treeview(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        if not (self.current_shop and self.current_cash_register):
            self.status_var.set("Pozycje: 0")
            return
        current_rows = [r for r in self.rows if r["shop"] == self.current_shop and r["cash_register"] == self.current_cash_register]
        for i, r in enumerate(current_rows, start=1):
            self.tree.insert("", tk.END, values=(i, r["code"], r["type"], r["notes"]))
        self.status_var.set(f"Pozycje: {len(current_rows)}")

    # --- Remove / Clear ---
    def remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Usuń", "Nie zaznaczono elementów.")
            return
        current_rows = [r for r in self.rows if r["shop"] == self.current_shop and r["cash_register"] == self.current_cash_register]
        for iid in sel:
            values = self.tree.item(iid, "values")
            idx = int(values[0]) - 1
            if 0 <= idx < len(current_rows):
                self.rows.remove(current_rows[idx])
        self.save_data()
        self.update_treeview()

    def clear_all(self):
        if not (self.current_shop and self.current_cash_register):
            return
        if messagebox.askyesno("Wyczyść", f"Czy na pewno wyczyścić listę kasy {self.current_cash_register} w sklepie {self.current_shop}?"):
            self.rows = [r for r in self.rows if not (r["shop"] == self.current_shop and r["cash_register"] == self.current_cash_register)]
            self.save_data()
            self.update_treeview()

    # --- Easter Eggs ---
    def neuron_count(self):
        neurons = random.randrange(1, 8)
        win = tk.Toplevel()
        win.title("Liczenie neuronów")
        width, height = 300, 120
        screen_width = win.winfo_screenwidth()
        screen_height = win.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        win.geometry(f"{width}x{height}+{x}+{y}")
        win.resizable(False, False)
        label = ttk.Label(win, text=f"Znaleziono {neurons}", anchor="center")
        label.pack(pady=20)
        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=10)
        def close_win():
            win.destroy()
        btn1 = ttk.Button(btn_frame, text="Nie, to musi być inaczej", command=close_win)
        btn1.pack(side=tk.LEFT, padx=5)
        btn2 = ttk.Button(btn_frame, text="Jeszcze jak!", command=close_win)
        btn2.pack(side=tk.LEFT, padx=5)
        win.transient()
        win.grab_set()
        win.wait_window()

def main():
    root = tk.Tk()
    app = InventoryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
