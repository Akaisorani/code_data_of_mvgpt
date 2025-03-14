import gradio as gr

# gradio可用颜色列表
# gr.themes.utils.colors.slate (石板色)
# gr.themes.utils.colors.gray (灰色)
# gr.themes.utils.colors.zinc (锌色)
# gr.themes.utils.colors.neutral (中性色)
# gr.themes.utils.colors.stone (石头色)
# gr.themes.utils.colors.red (红色)
# gr.themes.utils.colors.orange (橙色)
# gr.themes.utils.colors.amber (琥珀色)
# gr.themes.utils.colors.yellow (黄色)
# gr.themes.utils.colors.lime (酸橙色)
# gr.themes.utils.colors.green (绿色)
# gr.themes.utils.colors.emerald (祖母绿)
# gr.themes.utils.colors.teal (青蓝色)
# gr.themes.utils.colors.cyan (青色)
# gr.themes.utils.colors.sky (天蓝色)
# gr.themes.utils.colors.blue (蓝色)
# gr.themes.utils.colors.indigo (靛蓝色)
# gr.themes.utils.colors.violet (紫罗兰色)
# gr.themes.utils.colors.purple (紫色)
# gr.themes.utils.colors.fuchsia (洋红色)
# gr.themes.utils.colors.pink (粉红色)
# gr.themes.utils.colors.rose (玫瑰色)
from PIL import Image
import io
import base64


def adjust_theme():
    try:
        set_theme = gr.themes.Base()
        set_theme.set(
            body_background_fill="*background_fill_primary",
            body_text_color="*neutral_100",
            color_accent_soft="*neutral_700",
            background_fill_primary="*neutral_950",
            background_fill_secondary="*neutral_900",
            border_color_accent="*neutral_600",
            border_color_primary="*neutral_700",
            link_text_color_active="*secondary_500",
            link_text_color="*secondary_500",
            link_text_color_hover="*secondary_400",
            link_text_color_visited="*secondary_600",
            body_text_color_subdued="*neutral_400",
            shadow_spread="1px",
            block_background_fill="*neutral_800",
            block_border_color="*border_color_primary",
            block_border_width=None,
            block_info_text_color="*body_text_color_subdued",
            block_label_background_fill="*background_fill_secondary",
            block_label_border_color="*border_color_primary",
            block_label_border_width=None,
            block_label_text_color="*neutral_200",
            block_shadow=None,
            block_title_background_fill=None,
            block_title_border_color=None,
            block_title_border_width=None,
            block_title_text_color="*neutral_200",
            panel_background_fill="*background_fill_secondary",
            panel_border_color="*border_color_primary",
            panel_border_width=None,
            checkbox_background_color="*neutral_800",
            checkbox_background_color_focus="*checkbox_background_color",
            checkbox_background_color_hover="*checkbox_background_color",
            checkbox_background_color_selected="*secondary_600",
            checkbox_border_color="*neutral_700",
            checkbox_border_color_focus="*secondary_500",
            checkbox_border_color_hover="*neutral_600",
            checkbox_border_color_selected="*secondary_600",
            checkbox_border_width="*input_border_width",
            checkbox_label_background_fill="*button_secondary_background_fill",
            checkbox_label_background_fill_hover="*button_secondary_background_fill_hover",
            checkbox_label_background_fill_selected="*checkbox_label_background_fill",
            checkbox_label_border_color="*border_color_primary",
            checkbox_label_border_color_hover="*checkbox_label_border_color",
            checkbox_label_border_width="*input_border_width",
            checkbox_label_text_color="*body_text_color",
            checkbox_label_text_color_selected="*checkbox_label_text_color",
            error_background_fill="*background_fill_primary",
            error_border_color="*border_color_primary",
            error_border_width=None,
            error_text_color="#ef4444",
            input_background_fill="*neutral_700",
            input_background_fill_focus="*secondary_600",
            input_background_fill_hover="*input_background_fill",
            input_border_color="*border_color_primary",
            input_border_color_focus="*neutral_700",
            input_border_color_hover="*input_border_color",
            input_border_width=None,
            input_placeholder_color="*neutral_500",
            input_shadow=None,
            input_shadow_focus=None,
            loader_color=None,
            slider_color=None,
            stat_background_fill="*primary_500",
            table_border_color="*neutral_700",
            table_even_background_fill="*neutral_950",
            table_odd_background_fill="*neutral_900",
            table_row_focus="*color_accent_soft",
            button_border_width="*input_border_width",
            button_cancel_background_fill="*button_secondary_background_fill",
            button_cancel_background_fill_hover="*button_cancel_background_fill",
            button_cancel_border_color="*button_secondary_border_color",
            button_cancel_border_color_hover="*button_cancel_border_color",
            button_cancel_text_color="*button_secondary_text_color",
            button_cancel_text_color_hover="*button_cancel_text_color",
            button_primary_background_fill="*primary_700",
            button_primary_background_fill_hover="*button_primary_background_fill",
            button_primary_border_color="*primary_600",
            button_primary_border_color_hover="*button_primary_border_color",
            button_primary_text_color="white",
            button_primary_text_color_hover="*button_primary_text_color",
            button_secondary_background_fill="*neutral_600",
            button_secondary_background_fill_hover="*button_secondary_background_fill",
            button_secondary_border_color="*neutral_600",
            button_secondary_border_color_hover="*button_secondary_border_color",
            button_secondary_text_color="white",
            button_secondary_text_color_hover="*button_secondary_text_color",
        )
    except Exception as e:
        print(e)
        set_theme = None
        print('gradio版本较旧, 不能自定义字体和颜色')
    return set_theme


advanced_css = """
/* 设置表格的外边距为1em，内部单元格之间边框合并，空单元格显示. */
.markdown-body table {
    margin: 1em 0;
    border-collapse: collapse;
    empty-cells: show;
}

/* 设置表格单元格的内边距为5px，边框粗细为1.2px，颜色为--border-color-primary. */
.markdown-body th, .markdown-body td {
    border: 1.2px solid var(--border-color-primary);
    padding: 5px;
}

/* 设置表头背景颜色为rgba(175,184,193,0.2)，透明度为0.2. */
.markdown-body thead {
    background-color: rgba(175,184,193,0.2);
}

/* 设置表头单元格的内边距为0.5em和0.2em. */
.markdown-body thead th {
    padding: .5em .2em;
}

/* 去掉列表前缀的默认间距，使其与文本线对齐. */
.markdown-body ol, .markdown-body ul {
    padding-inline-start: 2em !important;
}

/* 设定聊天气泡的样式，包括圆角、最大宽度和阴影等. */
[class *= "message"] {
    border-radius: var(--radius-xl) !important;
    /* padding: var(--spacing-xl) !important; */
    /* font-size: var(--text-md) !important; */
    /* line-height: var(--line-md) !important; */
    /* min-height: calc(var(--text-md)*var(--line-md) + 2*var(--spacing-xl)); */
    /* min-width: calc(var(--text-md)*var(--line-md) + 2*var(--spacing-xl)); */
}
[data-testid = "bot"] {
    max-width: 95%;
    /* width: auto !important; */
    border-bottom-left-radius: 0 !important;
}
[data-testid = "user"] {
    max-width: 100%;
    /* width: auto !important; */
    border-bottom-right-radius: 0 !important;
}

/* 行内代码的背景设为淡灰色，设定圆角和间距. */
.markdown-body code {
    display: inline;
    white-space: break-spaces;
    border-radius: 6px;
    margin: 0 2px 0 2px;
    padding: .2em .4em .1em .4em;
    background-color: rgba(175,184,193,0.2);
}
/* 设定代码块的样式，包括背景颜色、内、外边距、圆角。 */
.markdown-body pre code {
    display: block;
    overflow: auto;
    white-space: pre;
    background-color: rgba(175,184,193,0.2);
    border-radius: 10px;
    padding: 1em;
    margin: 1em 2em 1em 0.5em;
}

"""
