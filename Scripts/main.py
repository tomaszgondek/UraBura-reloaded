import re
import csv
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# --- Rules for recognizing device types ---
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


# --- GUI ---
class InventoryApp:
    def __init__(self, root):
        self.root = root
        root.title("Inwentaryzacja - skanery kodów")
        root.geometry("1000x600")

        frm_top = ttk.Frame(root, padding=8)
        frm_top.pack(fill=tk.X)

        # Shop entry + combobox
        ttk.Label(frm_top, text="Sklep:").pack(side=tk.LEFT, padx=(0,6))
        self.shop_var = tk.StringVar()
        self.entry_shop = ttk.Entry(frm_top, textvariable=self.shop_var, width=8)
        self.entry_shop.pack(side=tk.LEFT, padx=(0,6))
        self.entry_shop.bind("<Return>", self.add_shop)

        self.shop_combo_var = tk.StringVar()
        self.shop_combo = ttk.Combobox(frm_top, textvariable=self.shop_combo_var, state="readonly", width=10)
        self.shop_combo.pack(side=tk.LEFT, padx=(0,12))
        self.shop_combo.bind("<<ComboboxSelected>>", self.switch_shop)

        self.btn_delete_shop = ttk.Button(frm_top, text="Usuń sklep", command=self.delete_current_shop)
        self.btn_delete_shop.pack(side=tk.LEFT, padx=(0,12))

        # Cash register entry + combobox
        ttk.Label(frm_top, text="Kasa:").pack(side=tk.LEFT, padx=(0,6))
        self.cash_register_var = tk.StringVar()
        self.entry_cash_register = ttk.Entry(frm_top, textvariable=self.cash_register_var, width=6)
        self.entry_cash_register.pack(side=tk.LEFT, padx=(0,6))
        self.entry_cash_register.bind("<Return>", self.add_cash_register)

        self.cash_register_combo_var = tk.StringVar()
        self.cash_register_combo = ttk.Combobox(frm_top, textvariable=self.cash_register_combo_var, state="readonly", width=10)
        self.cash_register_combo.pack(side=tk.LEFT, padx=(0,12))
        self.cash_register_combo.bind("<<ComboboxSelected>>", self.switch_cash_register)

        self.btn_delete_cash = ttk.Button(frm_top, text="Usuń kasę", command=self.delete_current_cash_register)
        self.btn_delete_cash.pack(side=tk.LEFT, padx=(0,12))

        # Code entry
        ttk.Label(frm_top, text="Kod (numer seryjny):").pack(side=tk.LEFT)
        self.code_var = tk.StringVar()
        self.entry_code = ttk.Entry(frm_top, textvariable=self.code_var, width=40)
        self.entry_code.pack(side=tk.LEFT, padx=(6,6))
        self.entry_code.bind("<Return>", self.on_submit)
        self.entry_code.focus_set()

        # Menubutton z rozwijanym menu
        self.menu_button = ttk.Menubutton(frm_top, text="Więcej funkcji")
        self.menu = tk.Menu(self.menu_button, tearoff=0)
        self.menu.add_command(label="Usuń zaznaczone", command=self.remove_selected)
        self.menu.add_command(label="Wyczyść listę", command=self.clear_all)
        self.menu.add_separator()
        self.menu.add_command(label="Eksportuj CSV", command=self.save_csv)
        self.menu.add_command(label="Importuj CSV", command=self.load_csv)
        self.menu_button["menu"] = self.menu
        self.menu_button.pack(side=tk.RIGHT, padx=(6, 0))

        # Treeview
        cols = ("lp", "code", "device_type", "timestamp", "notes")
        self.tree = ttk.Treeview(root, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("lp", text="#")
        self.tree.heading("code", text="Kod / S/N")
        self.tree.heading("device_type", text="Typ urządzenia")
        self.tree.heading("timestamp", text="Czas dodania")
        self.tree.heading("notes", text="Uwagi")
        self.tree.column("lp", width=40, anchor="center")
        self.tree.column("code", width=250, anchor="w")
        self.tree.column("device_type", width=180, anchor="center")
        self.tree.column("timestamp", width=160, anchor="center")
        self.tree.column("notes", width=200, anchor="w")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.tree.bind("<Double-1>", self.on_double_click)

        # Status
        frm_status = ttk.Frame(root, padding=6)
        frm_status.pack(fill=tk.X)
        self.status_var = tk.StringVar(value="Pozycje: 0")
        ttk.Label(frm_status, textvariable=self.status_var).pack(side=tk.LEFT)

        # Data storage
        self.rows = []  # list of dicts
        self.shops = []
        self.cash_registers = {}  # {shop: [list of cash registers]}
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

    # --- Shops ---
    def add_shop(self, event=None):
        shop = self.shop_var.get().strip()
        if not shop:
            return
        if shop not in self.shops:
            self.shops.append(shop)
            self.shops.sort(key=lambda x: int(x) if x.isdigit() else x)
            self.cash_registers[shop] = []
        self.current_shop = shop
        self.shop_combo['values'] = self.shops
        self.shop_combo_var.set(shop)
        self.shop_var.set("")
        self.update_treeview()

    def switch_shop(self, event=None):
        shop = self.shop_combo_var.get()
        if not shop:
            return
        self.current_shop = shop
        self.update_cash_register_combo()
        self.update_treeview()

    def delete_current_shop(self):
        if not self.current_shop:
            messagebox.showinfo("Usuń sklep", "Nie wybrano sklepu do usunięcia.")
            return
        shop = self.current_shop
        if not messagebox.askyesno("Usuń sklep", f"Czy na pewno usunąć sklep {shop}?"):
            return
        self.rows = [r for r in self.rows if r["shop"] != shop]
        self.shops.remove(shop)
        del self.cash_registers[shop]
        if self.shops:
            self.current_shop = self.shops[0]
            self.shop_combo['values'] = self.shops
            self.shop_combo_var.set(self.current_shop)
        else:
            self.current_shop = None
            self.shop_combo['values'] = []
            self.shop_combo_var.set("")
        self.current_cash_register = None
        self.update_treeview()

    # --- Cash registers ---
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
        self.update_cash_register_combo()
        self.cash_register_combo_var.set(cash_register)
        self.cash_register_var.set("")
        self.update_treeview()

    def update_cash_register_combo(self):
        if not self.current_shop:
            self.cash_register_combo['values'] = []
            return
        self.cash_register_combo['values'] = self.cash_registers[self.current_shop]

    def switch_cash_register(self, event=None):
        cash_register = self.cash_register_combo_var.get()
        if not cash_register:
            return
        self.current_cash_register = cash_register
        self.update_treeview()

    def delete_current_cash_register(self):
        if not self.current_cash_register or not self.current_shop:
            messagebox.showinfo("Usuń kasę", "Nie wybrano kasy do usunięcia.")
            return
        cash_register = self.current_cash_register
        if not messagebox.askyesno("Usuń kasę", f"Czy na pewno usunąć kasę {cash_register}?"):
            return
        self.rows = [r for r in self.rows if not (r["shop"] == self.current_shop and r["cash_register"] == cash_register)]
        self.cash_registers[self.current_shop].remove(cash_register)
        if self.cash_registers[self.current_shop]:
            self.current_cash_register = self.cash_registers[self.current_shop][0]
            self.cash_register_combo['values'] = self.cash_registers[self.current_shop]
            self.cash_register_combo_var.set(self.current_cash_register)
        else:
            self.current_cash_register = None
            self.cash_register_combo['values'] = []
            self.cash_register_combo_var.set("")
        self.update_treeview()

    # --- Treeview handling ---
    def update_treeview(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        if not (self.current_shop and self.current_cash_register):
            self.status_var.set("Pozycje: 0")
            return
        visible_rows = [r for r in self.rows if r["shop"] == self.current_shop and r["cash_register"] == self.current_cash_register]
        for idx, r in enumerate(visible_rows, start=1):
            self.tree.insert("", tk.END, values=(idx, r["code"], r["device_type"], r["timestamp"], r["notes"]))
        self.status_var.set(f"Pozycje: {len(visible_rows)}")

    def on_submit(self, event=None):
        if not (self.current_shop and self.current_cash_register):
            messagebox.showwarning("Brak sklepu/kasy", "Najpierw dodaj sklep i kasę.")
            return
        code = self.code_var.get().strip()
        if not code:
            return
        device_type = recognize_device_type(code)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.rows.append({
            "shop": self.current_shop,
            "cash_register": self.current_cash_register,
            "code": code,
            "device_type": device_type,
            "timestamp": timestamp,
            "notes": ""
        })
        self.update_treeview()
        self.code_var.set("")
        self.entry_code.focus_set()

    def on_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item_id:
            return
        x, y, width, height = self.tree.bbox(item_id, column)

        if column == "#2":  # code
            value = self.tree.set(item_id, column)
            entry = ttk.Entry(self.tree, width=40)
            entry.place(x=x, y=y, width=width, height=height)
            entry.insert(0, value)
            entry.focus_set()

            def save_code(event=None):
                new_val = entry.get().strip()
                device_type = recognize_device_type(new_val)
                self.tree.set(item_id, "code", new_val)
                self.tree.set(item_id, "device_type", device_type)
                for r in self.rows:
                    if (r["shop"], r["cash_register"], r["code"], r["timestamp"]) == (
                        self.current_shop, self.current_cash_register, value, self.tree.set(item_id, "timestamp")
                    ):
                        r["code"] = new_val
                        r["device_type"] = device_type
                        break
                entry.destroy()

            entry.bind("<Return>", save_code)
            entry.bind("<FocusOut>", lambda e: entry.destroy())

        elif column == "#3":  # device type
            current_val = self.tree.set(item_id, column)
            combo = ttk.Combobox(self.tree, values=self.device_types, state="readonly")
            combo.place(x=x, y=y, width=width, height=height)
            combo.set(current_val)
            combo.focus_set()

            def save_device_type(event=None):
                new_val = combo.get()
                self.tree.set(item_id, "device_type", new_val)
                for r in self.rows:
                    if (r["shop"], r["cash_register"], r["code"], r["device_type"], r["timestamp"]) == (
                        self.current_shop, self.current_cash_register, self.tree.set(item_id, "code"), current_val, self.tree.set(item_id, "timestamp")
                    ):
                        r["device_type"] = new_val
                        break
                combo.destroy()

            combo.bind("<<ComboboxSelected>>", save_device_type)
            combo.bind("<FocusOut>", lambda e: combo.destroy())

        elif column == "#5":  # notes
            value = self.tree.set(item_id, column)
            entry = ttk.Entry(self.tree, width=40)
            entry.place(x=x, y=y, width=width, height=height)
            entry.insert(0, value)
            entry.focus_set()

            def save_notes(event=None):
                new_val = entry.get().strip()
                self.tree.set(item_id, "notes", new_val)
                for r in self.rows:
                    if (r["shop"], r["cash_register"], r["code"], r["timestamp"]) == (
                        self.current_shop, self.current_cash_register, self.tree.set(item_id, "code"), self.tree.set(item_id, "timestamp")
                    ):
                        r["notes"] = new_val
                        break
                entry.destroy()

            entry.bind("<Return>", save_notes)
            entry.bind("<FocusOut>", lambda e: entry.destroy())

    # --- Removing and clearing ---
    def remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Usuń", "Nie zaznaczono elementów.")
            return
        for iid in sel:
            vals = self.tree.item(iid, "values")
            for i, r in enumerate(self.rows):
                if (r["shop"], r["cash_register"], r["code"], r["device_type"], r["timestamp"], r["notes"]) == (
                    self.current_shop, self.current_cash_register, vals[1], vals[2], vals[3], vals[4]
                ):
                    del self.rows[i]
                    break
            self.tree.delete(iid)
        self.update_treeview()

    def clear_all(self):
        if not (self.current_shop and self.current_cash_register):
            return
        if messagebox.askyesno("Wyczyść", f"Czy na pewno wyczyścić listę kasy {self.current_cash_register}?"):
            self.rows = [r for r in self.rows if not (r["shop"] == self.current_shop and r["cash_register"] == self.current_cash_register)]
            self.update_treeview()
            self.entry_code.focus_set()

    # --- CSV Import / Export ---
    def save_csv(self):
        if not self.rows:
            messagebox.showinfo("Zapis", "Brak danych do zapisania.")
            return
        default_name = f"inwentaryzacja_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=default_name,
                                            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["shop", "cash_register", "code", "device_type", "timestamp", "notes"])
                writer.writeheader()
                for row in self.rows:
                    writer.writerow(row)
            messagebox.showinfo("Zapis", f"Zapisano {len(self.rows)} pozycji do:\n{path}")
        except Exception as e:
            messagebox.showerror("Błąd zapisu", str(e))

    def load_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.rows = []
                self.shops = []
                self.cash_registers = {}
                for row in reader:
                    row = {k: row[k] for k in ["shop", "cash_register", "code", "device_type", "timestamp", "notes"]}
                    self.rows.append(row)
                    if row["shop"] not in self.shops:
                        self.shops.append(row["shop"])
                        self.cash_registers[row["shop"]] = []
                    if row["cash_register"] not in self.cash_registers[row["shop"]]:
                        self.cash_registers[row["shop"]].append(row["cash_register"])
                self.shops.sort(key=lambda x: int(x) if x.isdigit() else x)
                for shop in self.cash_registers:
                    self.cash_registers[shop].sort(key=lambda x: int(x) if x.isdigit() else x)
                if self.shops:
                    self.current_shop = self.shops[0]
                    self.shop_combo['values'] = self.shops
                    self.shop_combo_var.set(self.current_shop)
                    self.update_cash_register_combo()
                    if self.cash_registers[self.current_shop]:
                        self.current_cash_register = self.cash_registers[self.current_shop][0]
                        self.cash_register_combo_var.set(self.current_cash_register)
                self.update_treeview()
            messagebox.showinfo("Wczytano", f"Wczytano dane z:\n{path}")
        except Exception as e:
            messagebox.showerror("Błąd wczytywania", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = InventoryApp(root)
    root.mainloop()
