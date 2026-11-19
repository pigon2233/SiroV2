//! SIRO 語音監測（最小版）：一個視窗顯示目前階段、進度、預計完成時間與 mel loss 折線圖。
//!
//! 只讀檔案（透過 \\wsl.localhost 讀 WSL 裡的訓練 log／進度檔），背景執行緒每 5 秒重新讀取；
//! 關掉視窗不影響任何工作。路徑設定在 siro-monitor.toml（exe 旁邊或目前資料夾）。
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod data;

use std::sync::{Arc, Mutex};
use std::time::Duration;

use eframe::egui;
use egui_plot::{Line, Plot, PlotPoints};

use data::{Config, Snapshot};

fn main() -> eframe::Result {
    let config = Config::load();
    let snapshot = Arc::new(Mutex::new(Snapshot::default()));
    {
        let snapshot = Arc::clone(&snapshot);
        std::thread::spawn(move || loop {
            let fresh = data::collect(&config);
            if let Ok(mut s) = snapshot.lock() {
                *s = fresh;
            }
            std::thread::sleep(Duration::from_secs(5));
        });
    }
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_title("SIRO 語音監測")
            .with_inner_size([520.0, 560.0])
            .with_min_inner_size([380.0, 360.0]),
        ..Default::default()
    };
    eframe::run_native(
        "SIRO 語音監測",
        options,
        Box::new(move |cc| {
            install_cjk_font(&cc.egui_ctx);
            Ok(Box::new(MonitorApp { snapshot }))
        }),
    )
}

/// egui 內建字型沒有中文；用 Windows 內建的微軟正黑體。
fn install_cjk_font(ctx: &egui::Context) {
    let candidates = [r"C:\Windows\Fonts\msjh.ttc", r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\mingliu.ttc"];
    let Some(bytes) = candidates.iter().find_map(|p| std::fs::read(p).ok()) else {
        return;
    };
    let mut fonts = egui::FontDefinitions::default();
    fonts.font_data.insert("cjk".into(), Arc::new(egui::FontData::from_owned(bytes)));
    for family in [egui::FontFamily::Proportional, egui::FontFamily::Monospace] {
        fonts.families.entry(family).or_default().push("cjk".into());
    }
    ctx.set_fonts(fonts);
}

struct MonitorApp {
    snapshot: Arc<Mutex<Snapshot>>,
}

impl eframe::App for MonitorApp {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        ui.ctx().request_repaint_after(Duration::from_secs(5));
        let snap = self.snapshot.lock().map(|s| s.clone()).unwrap_or_default();
        // 目前階段：有訓練 log 就看訓練，否則看資料準備。
        let training = !snap.train.loss.is_empty() || snap.train.state != "還沒有訓練";
        let (stage, state, fraction, rows) = if training {
            ("訓練", &snap.train.state, snap.train.fraction, &snap.train.rows)
        } else {
            ("資料準備", &snap.prep.state, snap.prep.fraction, &snap.prep.rows)
        };
        egui::Frame::NONE.inner_margin(12.0).show(ui, |ui| {
            ui.heading(format!("{stage}：{state}"));
            ui.add_space(4.0);
            if let Some(f) = fraction {
                ui.add(egui::ProgressBar::new(f.clamp(0.0, 1.0)).show_percentage());
            }
            ui.add_space(6.0);
            egui::Grid::new("info").num_columns(2).spacing([16.0, 6.0]).show(ui, |ui| {
                for (k, v) in rows {
                    ui.weak(k);
                    ui.label(v);
                    ui.end_row();
                }
            });
            if training {
                ui.add_space(10.0);
                ui.strong("mel loss（越低越好）");
                let loss = &snap.train.loss;
                let points: PlotPoints = loss
                    .iter()
                    .enumerate()
                    .map(|(i, r)| {
                        let lo = i.saturating_sub(8);
                        let avg = loss[lo..=i].iter().map(|x| x[1]).sum::<f64>() / (i - lo + 1) as f64;
                        [r[0], avg]
                    })
                    .collect();
                Plot::new("mel")
                    .height(ui.available_height().max(140.0) - 24.0)
                    .allow_scroll(false)
                    .allow_zoom(false)
                    .allow_drag(false)
                    .show(ui, |plot| {
                        plot.line(Line::new("mel", points).color(egui::Color32::from_rgb(30, 136, 229)).width(2.0));
                    });
            }
            ui.weak(format!("{} 更新・每 5 秒自動更新・關掉視窗不影響訓練", snap.updated));
        });
    }
}
