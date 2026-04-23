from fpdf import FPDF
import io

html = """
<h1 align="center">Test Authorization</h1>
<p>This is a test of <b>bold</b> and <i>italic</i> and <u>underlined</u> text.</p>
<p style="font-size: 20px">Big text</p>
<table border="1" width="100%">
    <thead>
        <tr>
            <th>#</th>
            <th>Name</th>
            <th>RG</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>1</td>
            <td>John Doe</td>
            <td>12345</td>
        </tr>
    </tbody>
</table>
"""

pdf = FPDF()
pdf.add_page()
pdf.set_font("helvetica", size=12)
pdf.write_html(html)
pdf.output("scratch/test.pdf")
print("PDF generated successfully")
