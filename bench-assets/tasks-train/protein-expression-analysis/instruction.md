You'll be working with metabolite abundance data from a gut microbiome study. Open `metabolite_abundance.xlsx` - it has two sheets: "Task" is where you'll do your work, and "Data" contains the raw abundance values.

## What's this about?

We have quantitative metabolomics data from fecal samples comparing healthy individuals vs patients with inflammatory bowel disease (IBD). Your job is to find which metabolites show significant differences between the two groups.

## Steps

### 1. Pull the abundance data

The Data sheet has log2-transformed abundance values for 150 metabolites across 40 samples. For the 8 target metabolites in column A (rows 8-15), look up their abundance values for the 12 samples in row 7. Put these in cells C8:N15 on the Task sheet.

You'll need to match on both metabolite ID and sample name. INDEX-MATCH works well for this kind of two-way lookup, though VLOOKUP or other approaches are fine too.

### 2. Calculate group statistics

Row 6 shows which samples are "Healthy" vs "Diseased" (highlighted in blue). For each metabolite, calculate:
- Mean and standard deviation for healthy samples
- Mean and standard deviation for diseased samples

The data is already log2-transformed, so regular mean and stdev are appropriate here.

Put your results in the yellow cells, rows 19-22, columns B-I.

### 3. Fold change calculations

For each metabolite (remember the data is already log2-transformed):
- Log2 Fold Change = Diseased Mean - Healthy Mean
- Fold Change = 2^(Log2 Fold Change)

Fill in columns C and D, rows 27-34 (yellow cells).

## A few things to watch out for

- Don't mess with the file format, colors, or fonts
- No macros or VBA code
- Use formulas, not hard-coded numbers
- Sample names in the Data sheet have prefixes like "FECAL_SUBJ01_Batch01"
