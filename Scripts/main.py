import re
import csv
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# --- Reguły rozpoznawania urządzeń ---
def rozpoznaj_typ(kod: str) -> str:
    s = kod.strip()
    if not s:
        return "Nieznany"

    if re.fullmatch(r'\d{20,}', s):
        return "Terminal płatniczy"

    if re.fullmatch(r'\d{2}[A-Z]\d{7,}', s):
        return "Komputer kasowy Beetle A"

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
class Inwentaryzator:
    def __init__(self, root):
        self.root = root
        root.title("UraBura 2.0")
        root.geometry("1250x550")

        frm_top = ttk.Frame(root, padding=8)
        frm_top.pack(fill=tk.X)

        # Kasa - Entry do dodawania nowych kas
        ttk.Label(frm_top, text="Dodaj kasę:").pack(side=tk.LEFT, padx=(0,6))
        self.kasa_var = tk.StringVar()
        self.entry_kasa = ttk.Entry(frm_top, textvariable=self.kasa_var, width=6)
        self.entry_kasa.pack(side=tk.LEFT, padx=(0,12))
        self.entry_kasa.bind("<Return>", self.add_kasa)

        # Import CSV
        self.btn_import = ttk.Button(frm_top, text="Import CSV", command=self.import_csv)
        self.btn_import.pack(side=tk.RIGHT, padx=(6, 0))

        # Combobox do wyboru aktualnej kasy
        ttk.Label(frm_top, text="Wybierz kasę:").pack(side=tk.LEFT, padx=(6,6))
        self.kasa_combo_var = tk.StringVar()
        self.kasa_combo = ttk.Combobox(frm_top, textvariable=self.kasa_combo_var, state="readonly", width=6)
        self.kasa_combo.pack(side=tk.LEFT, padx=(0,12))
        self.kasa_combo.bind("<<ComboboxSelected>>", self.on_kasa_selected)

        # Kod entry
        ttk.Label(frm_top, text="Kod (numer seryjny):").pack(side=tk.LEFT, padx=(6,6))
        self.kod_var = tk.StringVar()
        self.entry_kod = ttk.Entry(frm_top, textvariable=self.kod_var, width=40)
        self.entry_kod.pack(side=tk.LEFT, padx=(6,6))
        self.entry_kod.bind("<Return>", self.on_submit)
        self.entry_kod.focus_set()

        # Submit button
        self.btn_add = ttk.Button(frm_top, text="Dodaj (Enter)", command=self.on_submit)
        self.btn_add.pack(side=tk.LEFT, padx=(6,6))

        # Delete list button
        self.btn_delete_kasa = ttk.Button(frm_top, text="Usuń kasę", command=self.delete_current_kasa)
        self.btn_delete_kasa.pack(side=tk.LEFT, padx=(6, 6))

        # Buttons: Save, Clear, Remove selected
        self.btn_save = ttk.Button(frm_top, text="Zapisz CSV", command=self.save_csv)
        self.btn_save.pack(side=tk.RIGHT, padx=(6,0))
        self.btn_clear = ttk.Button(frm_top, text="Wyczyść listę", command=self.clear_all)
        self.btn_clear.pack(side=tk.RIGHT, padx=(6,0))
        self.btn_remove = ttk.Button(frm_top, text="Usuń zaznaczone", command=self.remove_selected)
        self.btn_remove.pack(side=tk.RIGHT, padx=(6,0))

        # Treeview (lista wyników)
        cols = ("lp", "kod", "typ", "czas")
        self.tree = ttk.Treeview(root, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("lp", text="#")
        self.tree.heading("kod", text="Kod / S/N")
        self.tree.heading("typ", text="Typ urządzenia")
        self.tree.heading("czas", text="Czas dodania")
        self.tree.column("lp", width=40, anchor="center")
        self.tree.column("kod", width=300, anchor="w")
        self.tree.column("typ", width=180, anchor="center")
        self.tree.column("czas", width=160, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.tree.bind("<Double-1>", self.on_double_click)

        # status (liczniki)
        frm_status = ttk.Frame(root, padding=6)
        frm_status.pack(fill=tk.X)
        self.status_var = tk.StringVar(value="Pozycje: 0")
        ttk.Label(frm_status, textvariable=self.status_var).pack(side=tk.LEFT)

        # data store
        self.rows = []  # wszystkie wpisy {kasa, kod, typ, czas}
        self.kasy = []  # lista numerów kas
        self.current_kasa = None  # aktualnie wyświetlana kasa

        # dostępne typy urządzeń
        self.typy_urzadzen = [
            "Nieznany",
            "Terminal płatniczy",
            "Komputer kasowy Beetle A",
            "Komputer kasowy IPOS+",
            "Komputer kasowy MIII",
            "Drukarka fiskalna N/S",
            "Drukarka fiskalna N/U",
            "Skaner",
            "Tacka RFID",
            "Kosz"
        ]

    # --- Funkcje obsługi kas ---
    def add_kasa(self, event=None):
        kasa = self.kasa_var.get().strip()
        if not kasa:
            return
        if kasa not in self.kasy:
            self.kasy.append(kasa)
            # sortowanie numeryczne
            try:
                self.kasy.sort(key=lambda x: int(x))
            except ValueError:
                self.kasy.sort()  # fallback, jeśli nie da się zamienić na int
            self.kasa_combo['values'] = self.kasy
        self.current_kasa = kasa
        self.kasa_combo_var.set(kasa)
        self.kasa_var.set("")
        self.update_treeview()
        self.entry_kod.focus_set()

    def on_kasa_selected(self, event=None):
        kasa = self.kasa_combo_var.get()
        if kasa:
            self.current_kasa = kasa
            self.update_treeview()

    def update_treeview(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        if not self.current_kasa:
            return
        visible_rows = [r for r in self.rows if r["kasa"] == self.current_kasa]
        for idx, r in enumerate(visible_rows, start=1):
            self.tree.insert("", tk.END, values=(idx, r["kod"], r["typ"], r["czas"]))
        self.status_var.set(f"Pozycje: {len(visible_rows)}")

    def delete_current_kasa(self):
        if not self.current_kasa:
            messagebox.showinfo("Usuń kasę", "Nie wybrano kasy do usunięcia.")
            return
        kasa = self.current_kasa
        if not messagebox.askyesno("Usuń kasę", f"Czy na pewno usunąć całą kasę {kasa}?"):
            return
        # usuń wszystkie wpisy dla tej kasy
        self.rows = [r for r in self.rows if r["kasa"] != kasa]
        # usuń kasę z listy
        self.kasy.remove(kasa)
        self.kasa_combo['values'] = self.kasy
        # ustaw nową kasę
        if self.kasy:
            self.current_kasa = self.kasy[0]
            self.kasa_combo_var.set(self.current_kasa)
        else:
            self.current_kasa = None
            self.kasa_combo_var.set("")
        self.update_treeview()

    # --- Dodawanie pozycji ---
    def on_submit(self, event=None):
        if not self.current_kasa:
            messagebox.showwarning("Brak kasy", "Najpierw dodaj kasę.")
            return
        kod = self.kod_var.get().strip()
        if not kod:
            return

        kasa = self.current_kasa
        typ = rozpoznaj_typ(kod)
        czas = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.rows.append({"kasa": kasa, "kod": kod, "typ": typ, "czas": czas})
        self.update_treeview()

        self.kod_var.set("")
        self.entry_kod.focus_set()

    # --- Edycja Treeview ---
    def on_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item_id:
            return

        x, y, width, height = self.tree.bbox(item_id, column)

        if column == "#2":  # edycja kodu
            value = self.tree.set(item_id, column)
            entry = ttk.Entry(self.tree, width=40)
            entry.place(x=x, y=y, width=width, height=height)
            entry.insert(0, value)
            entry.focus_set()

            def save_edit(event=None):
                new_val = entry.get().strip()
                typ = rozpoznaj_typ(new_val)
                czas = self.tree.set(item_id, "czas")

                self.tree.set(item_id, "kod", new_val)
                self.tree.set(item_id, "typ", typ)

                for r in self.rows:
                    if (r["kasa"], r["kod"], r["typ"], r["czas"]) == (
                        self.tree.set(item_id, "kasa"),
                        value,
                        self.tree.set(item_id, "typ"),
                        czas
                    ):
                        r["kod"] = new_val
                        r["typ"] = typ
                        break

                entry.destroy()

            entry.bind("<Return>", save_edit)
            entry.bind("<FocusOut>", lambda e: entry.destroy())

        elif column == "#3":  # edycja typu urządzenia
            current_val = self.tree.set(item_id, column)
            combo = ttk.Combobox(self.tree, values=self.typy_urzadzen, state="readonly")
            combo.place(x=x, y=y, width=width, height=height)
            combo.set(current_val)
            combo.focus_set()

            def save_combo(event=None):
                new_val = combo.get()
                self.tree.set(item_id, "typ", new_val)

                for r in self.rows:
                    if (r["kasa"], r["kod"], r["typ"], r["czas"]) == (
                        self.tree.set(item_id, "kasa"),
                        self.tree.set(item_id, "kod"),
                        current_val,
                        self.tree.set(item_id, "czas")
                    ):
                        r["typ"] = new_val
                        break
                combo.destroy()

            combo.bind("<<ComboboxSelected>>", save_combo)
            combo.bind("<FocusOut>", lambda e: combo.destroy())

    # --- Usuwanie i czyszczenie ---
    def remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Usuń", "Nie zaznaczono elementów.")
            return
        for iid in sel:
            vals = self.tree.item(iid, "values")
            for i, r in enumerate(self.rows):
                if (r["kasa"], r["kod"], r["typ"], r["czas"]) == tuple(vals):
                    del self.rows[i]
                    break
            self.tree.delete(iid)
        self.update_treeview()

    def clear_all(self):
        if not self.current_kasa:
            return
        if messagebox.askyesno("Wyczyść", f"Czy na pewno wyczyścić listę kasy {self.current_kasa}?"):
            self.rows = [r for r in self.rows if r["kasa"] != self.current_kasa]
            self.update_treeview()
            self.entry_kod.focus_set()

    # --- Zapis CSV ---
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
                writer = csv.DictWriter(f, fieldnames=["kasa", "kod", "typ", "czas"])
                writer.writeheader()
                for row in self.rows:
                    writer.writerow(row)
            messagebox.showinfo("Zapis", f"Zapisano {len(self.rows)} pozycji do:\n{path}")
        except Exception as e:
            messagebox.showerror("Błąd zapisu", str(e))

    def import_csv(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    # Sprawdź poprawne pola
                    if not all(k in row for k in ["kasa", "kod", "typ", "czas"]):
                        continue
                    # dodaj kasę jeśli nowa
                    kasa = row["kasa"]
                    if kasa not in self.kasy:
                        self.kasy.append(kasa)
                    # dodaj wiersz
                    self.rows.append({
                        "kasa": row["kasa"],
                        "kod": row["kod"],
                        "typ": row["typ"],
                        "czas": row["czas"]
                    })
                    count += 1

                # sortowanie kas numerycznie
                try:
                    self.kasy.sort(key=lambda x: int(x))
                except ValueError:
                    self.kasy.sort()
                self.kasa_combo['values'] = self.kasy
                if count > 0 and not self.current_kasa:
                    self.current_kasa = self.kasy[0]
                    self.kasa_combo_var.set(self.current_kasa)
                self.update_treeview()
                messagebox.showinfo("Import CSV", f"Wczytano {count} pozycji z:\n{path}")
        except Exception as e:
            messagebox.showerror("Błąd importu", str(e))


def main():
    root = tk.Tk()
    app = Inwentaryzator(root)
    root.mainloop()


if __name__ == "__main__":
    main()
