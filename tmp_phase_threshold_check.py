import pandas as pd
df = pd.read_csv(r"C:\Users\SOhtani2024\visual_hazard_project\reports\phase_component_distributions\case_phase_component_distribution_summary.csv")
sub = df[(df["phase_level"]=="Level-1") & (df["component"]=="legacy_badness_alias")]
for q in ["p90","p95","p99"]:
    col = "frac_ge_global_" + q
    print("---", q, "---")
    print((sub.groupby("phase_label")[col].median()*100).round(1))
print("--- n cases per phase ---")(base) PS C:\Users\SOhtani2024\visual_hazard_project> Write-Host "=== A. 一時スクリプトで工程別閾値中央値を集計 ==="
=== A. 一時スクリプトで工程別閾値中央値を集計 ===
(base) PS C:\Users\SOhtani2024\visual_hazard_project> @'
>> import pandas as pd
>> df = pd.read_csv(r"C:\Users\SOhtani2024\visual_hazard_project\reports\phase_component_distributions\case_phase_component_distribution_summary.csv")
>> sub = df[(df["phase_level"]=="Level-1") & (df["component"]=="legacy_badness_alias")]
>> for q in ["p90","p95","p99"]:
>>     col = "frac_ge_global_" + q
>>     print("---", q, "---")
>>     print((sub.groupby("phase_label")[col].median()*100).round(1))
>> print("--- n cases per phase ---")
>> print(sub.groupby("phase_label")["case_id"].nunique())
>> '@ | Set-Content -Encoding UTF8 "$vh\tmp_phase_threshold_check.py"
(base) PS C:\Users\SOhtani2024\visual_hazard_project> python "$vh\tmp_phase_threshold_check.py"
  File "C:\Users\SOhtani2024\visual_hazard_project\tmp_phase_threshold_check.py", line 5
        col = "frac_ge_global_" + q
    ^
SyntaxError: invalid non-printable character U+00A0
(base) PS C:\Users\SOhtani2024\visual_hazard_project>
(base) PS C:\Users\SOhtani2024\visual_hazard_project> Write-Host "`n=== B. clinical_numeric_column_inventory.csv（列一覧） ==="

=== B. clinical_numeric_column_inventory.csv（列一覧） ===
(base) PS C:\Users\SOhtani2024\visual_hazard_project> Get-Content "$vh\reports\clinical_linkage_clean\clinical_numeric_column_inventory.csv"
clinical_numeric_col
operation_time_min
blood_loss_g
age
謇玖｡捺凾髢・(蛻・
陦謎ｸｭ蜃ｺ陦驥・gr)
RATS_蟷ｴ鮨｢
operation_time_available
blood_loss_available
original_case_id
video_exists
annotation_v2_exists
in_remaining_folder
include_candidate
include_level0
include_level1
include_level2
謇玖｡楢｡灘ｼ・
(base) PS C:\Users\SOhtani2024\visual_hazard_project>
(base) PS C:\Users\SOhtani2024\visual_hazard_project> Write-Host "`n=== C. case_visual_hazard_clinical_linkage.csv のヘッダーと先頭2行 ==="

=== C. case_visual_hazard_clinical_linkage.csv のヘッダーと先頭2行 ===
(base) PS C:\Users\SOhtani2024\visual_hazard_project> Get-Content "$vh\reports\clinical_linkage_clean\case_visual_hazard_clinical_linkage.csv" -TotalCount 3
case_id,n_frames,estimated_duration_sec,sample_interval_sec,frac_visual_hazard_any_p95,seconds_visual_hazard_any_p95,max_consecutive_seconds_visual_hazard_any_p95,frac_clean_reference_candidate_p95,seconds_clean_reference_candidate_p95,mean_hazard_component_count_p95,frac_structural_visibility_loss_ge_p95,seconds_structural_visibility_loss_ge_p95,frac_center_low_structure_area_ge_p95,seconds_center_low_structure_area_ge_p95,frac_whiteout_ge_p95,seconds_whiteout_ge_p95,frac_low_light_or_blackout_ge_p95,seconds_low_light_or_blackout_ge_p95,frac_visual_hazard_any_p99,seconds_visual_hazard_any_p99,max_consecutive_seconds_visual_hazard_any_p99,frac_clean_reference_candidate_p99,seconds_clean_reference_candidate_p99,mean_hazard_component_count_p99,frac_structural_visibility_loss_ge_p99,seconds_structural_visibility_loss_ge_p99,frac_center_low_structure_area_ge_p99,seconds_center_low_structure_area_ge_p99,frac_whiteout_ge_p99,seconds_whiteout_ge_p99,frac_low_light_or_blackout_ge_p99,seconds_low_light_or_blackout_ge_p99,case_uid,year,original_case_id,surgery_date,sex,age,procedure_raw,procedure_group,side_raw,side,target_raw,target_lobe_or_segment,robotic_label,video_exists,frames_exists,annotation_v2_exists,metadata_exists,in_remaining_folder,include_candidate,include_level0,include_level1,include_level2,operation_time_min,blood_loss_g,operation_time_available,blood_loss_available,exclusion_reason,audit_note,manual_correction_note,RATS_謇玖｡捺律,RATS_諤ｧ蛻･謗ｨ螳・RATS_蟷ｴ鮨｢,derived_side,derived_procedure_type,derived_target_lobe_or_segment,derived_robotic_label,謇玖｡捺凾髢・(蛻・,陦謎ｸｭ蜃ｺ陦驥・gr),RATS_Method,RATS_Method2,謇玖｡灘・,閧ｺ蛻・勁遽・峇,蛻・勁閧ｺ闡・蛹ｺ蝓溷・髯､,驛ｨ蛻・・髯､,謇玖｡楢｡灘ｼ・level1_DrainClosure__seconds_visual_hazard_any_p95,level1_LeakHemostasis__seconds_visual_hazard_any_p95,level1_NoLabel__seconds_visual_hazard_any_p95,level1_PortDockExplore__seconds_visual_hazard_any_p95,level1_PortPreparation__seconds_visual_hazard_any_p95,level1_SpecimenPathway__seconds_visual_hazard_any_p95,level1_SpecimenRetrieval__seconds_visual_hazard_any_p95,level1_DrainClosure__frac_visual_hazard_any_p95,level1_LeakHemostasis__frac_visual_hazard_any_p95,level1_NoLabel__frac_visual_hazard_any_p95,level1_PortDockExplore__frac_visual_hazard_any_p95,level1_PortPreparation__frac_visual_hazard_any_p95,level1_SpecimenPathway__frac_visual_hazard_any_p95,level1_SpecimenRetrieval__frac_visual_hazard_any_p95,level1_DrainClosure__max_consecutive_seconds_visual_hazard_any_p95,level1_LeakHemostasis__max_consecutive_seconds_visual_hazard_any_p95,level1_NoLabel__max_consecutive_seconds_visual_hazard_any_p95,level1_PortDockExplore__max_consecutive_seconds_visual_hazard_any_p95,level1_PortPreparation__max_consecutive_seconds_visual_hazard_any_p95,level1_SpecimenPathway__max_consecutive_seconds_visual_hazard_any_p95,level1_SpecimenRetrieval__max_consecutive_seconds_visual_hazard_any_p95,level1_DrainClosure__seconds_visual_hazard_any_p99,level1_LeakHemostasis__seconds_visual_hazard_any_p99,level1_NoLabel__seconds_visual_hazard_any_p99,level1_PortDockExplore__seconds_visual_hazard_any_p99,level1_PortPreparation__seconds_visual_hazard_any_p99,level1_SpecimenPathway__seconds_visual_hazard_any_p99,level1_SpecimenRetrieval__seconds_visual_hazard_any_p99,level1_DrainClosure__frac_visual_hazard_any_p99,level1_LeakHemostasis__frac_visual_hazard_any_p99,level1_NoLabel__frac_visual_hazard_any_p99,level1_PortDockExplore__frac_visual_hazard_any_p99,level1_PortPreparation__frac_visual_hazard_any_p99,level1_SpecimenPathway__frac_visual_hazard_any_p99,level1_SpecimenRetrieval__frac_visual_hazard_any_p99,level1_DrainClosure__max_consecutive_seconds_visual_hazard_any_p99,level1_LeakHemostasis__max_consecutive_seconds_visual_hazard_any_p99,level1_NoLabel__max_consecutive_seconds_visual_hazard_any_p99,level1_PortDockExplore__max_consecutive_seconds_visual_hazard_any_p99,level1_PortPreparation__max_consecutive_seconds_visual_hazard_any_p99,level1_SpecimenPathway__max_consecutive_seconds_visual_hazard_any_p99,level1_SpecimenRetrieval__max_consecutive_seconds_visual_hazard_any_p99
CASE001,10235,10235.0,1.0,0.1383488031265266,1416.0,54.0,0.8616511968734734,8819.0,0.1969711773326819,0.0465070835368832,476.0,0.073961895456766,757.0,0.0243282852955544,249.0,0.0521739130434782,534.0,0.0205178309721543,210.0,19.0,0.9794821690278456,10025.0,0.0269662921348314,0.0061553492916463,63.0,0.0067415730337078,69.0,0.0033219345383488,34.0,0.0107474352711284,110.0,RATS2023_CASE001,2023,CASE001,2023-12-28,逕ｷ,76,蛹ｺ蝓溷・髯､,segmentectomy,蜿ｳ,Right,蜿ｳ蠎募玄蝓・蜿ｳ蠎募玄蝓・robotic,True,True,True,True,False,True,True,True,True,270.0,5.0,True,True,,,,2023-12-28,逕ｷ,76,蜿ｳ,蛹ｺ蝓溷・髯､,蜿ｳ蠎募玄蝓・robotic,270.0,5.0,RATS,蜿ｳ荳句玄蛻・ 蜿ｳ, 蛹ｺ蝓溷・髯､,, 蠎募玄,,繝ｭ繝懊ャ繝域髪謠ｴ荳句承閧ｺ蠎募玄蝓溷・髯､+ND2a-1,370.0,461.0,1.0,75.0,,509.0,,0.2846153846153846,0.3432613551749814,1.0,0.1363636363636363,,0.0722908677744638,,34.0,39.0,1.0,16.0,,54.0,,41.0,80.0,0.0,13.0,,76.0,,0.0315384615384615,0.0595681310498883,0.0,0.0236363636363636,,0.0107939213179946,,4.0,11.0,0.0,1.0,,19.0,
CASE003,10919,10919.0,1.0,0.1428702262111915,1560.0,113.0,0.8571297737888085,9359.0,0.2360106236834875,0.0825167139847971,901.0,0.0927740635589339,1013.0,0.0199651982782306,218.0,0.0407546478615257,445.0,0.0403883139481637,441.0,47.0,0.9596116860518362,10478.0,0.05595750526605,0.0156607747962267,171.0,0.0173092774063558,189.0,0.0049455078303873,54.0,0.0180419452330799,197.0,RATS2023_CASE003,2023,CASE003,2023-12-26,螂ｳ,52,蛹ｺ蝓溷・髯､,segmentectomy,蟾ｦ,Left,蟾ｦ荳雁､ｧ蛹ｺ蝓・蟾ｦ荳雁､ｧ蛹ｺ蝓・robotic,True,True,True,True,False,True,True,True,True,207.0,11.0,True,True,,,,2023-12-26,螂ｳ,52,蟾ｦ,蛹ｺ蝓溷・髯､,蟾ｦ荳雁､ｧ蛹ｺ蝓・robotic,207.0,11.0,RATS,蟾ｦ荳雁､ｧ蛹ｺ蛻・ 蟾ｦ, 蛹ｺ蝓溷・髯､,, 荳雁､ｧ蛹ｺ,,RATS荳句ｷｦ荳雁､ｧ蛹ｺ蝓溷・髯､・九Μ繝ｳ繝醍ｯ驛ｭ貂・D1a,139.0,678.0,3.0,386.0,,354.0,,0.3270588235294118,0.4529058116232465,0.4285714285714285,0.2928679817905918,,0.0461418143899895,,30.0,113.0,3.0,29.0,,53.0,,45.0,169.0,0.0,104.0,,123.0,,0.1058823529411764,0.1128924515698062,0.0,0.0789074355083459,,0.0160323253388946,,6.0,28.0,0.0,9.0,,47.0,
(base) PS C:\Users\SOhtani2024\visual_hazard_project>
print(sub.groupby("phase_label")["case_id"].nunique())
